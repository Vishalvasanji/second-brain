#!/usr/bin/env python3
"""
Memory scoring algorithms for Second Brain v2

Implements relevance scoring with decay, frequency boosting, and category weights.
"""

import math
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from collections import Counter


def calculate_memory_score(
    memory: Dict[str, Any],
    config: Dict[str, Any],
    reference_date: Optional[datetime] = None
) -> float:
    """
    Calculate relevance score for a memory item.
    
    Args:
        memory: Memory dictionary with text, category, timestamp, etc.
        config: Scoring configuration from config.yaml
        reference_date: Date to calculate decay from (default: now)
    
    Returns:
        Float score (0.0 to max_score)
    """
    if reference_date is None:
        reference_date = datetime.now()
    
    # Extract scoring config
    scoring_config = config.get("scoring", {})
    decay_half_life = scoring_config.get("decay_half_life_days", 14)
    category_weights = scoring_config.get("category_weights", {})
    frequency_boost = scoring_config.get("frequency_boost", 1.2)
    max_score = scoring_config.get("max_score", 5.0)
    
    # Base score starts at 1.0
    score = 1.0
    
    # Apply category weight
    category = memory.get("category", "transient").lower()
    category_weight = category_weights.get(category, 1.0)
    score *= category_weight
    
    # Apply recency decay (exponential decay with half-life)
    memory_date = parse_memory_timestamp(memory.get("timestamp"))
    if memory_date:
        days_old = (reference_date - memory_date).days
        if days_old > 0:
            # Exponential decay: score * (0.5 ^ (days_old / half_life))
            decay_factor = 0.5 ** (days_old / decay_half_life)
            score *= decay_factor
    
    # Apply frequency boost
    frequency = memory.get("frequency", 1)
    if frequency > 1:
        # Logarithmic boost for frequency
        boost = 1 + math.log(frequency) * (frequency_boost - 1)
        score *= boost
    
    # Apply entity boost (memories with many entities are often more important)
    entities = memory.get("entities", [])
    if len(entities) > 2:  # More than 2 entities mentioned
        entity_boost = 1 + 0.1 * min(len(entities) - 2, 3)  # Cap boost at 3 extra entities
        score *= entity_boost
    
    # Apply completion penalty for completed action items
    if category == "action_items":
        text = memory.get("text", "").lower()
        if "[x]" in text or "completed" in text or "done" in text:
            score *= 0.3  # Reduce score for completed items
    
    # Cap at maximum score
    return min(score, max_score)


def parse_memory_timestamp(timestamp: Any) -> Optional[datetime]:
    """Parse various timestamp formats into datetime."""
    if isinstance(timestamp, datetime):
        return timestamp
    
    if isinstance(timestamp, str):
        # Try various formats
        formats = [
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%dT%H:%M:%S.%f",
            "%Y-%m-%d",
        ]
        
        for fmt in formats:
            try:
                return datetime.strptime(timestamp, fmt)
            except ValueError:
                continue
    
    return None


def calculate_frequency_scores(memories: List[Dict[str, Any]]) -> Dict[str, int]:
    """
    Calculate frequency scores for similar memories.
    
    Groups memories by semantic similarity and counts occurrences.
    """
    # Simple implementation: group by first 50 characters of text
    text_groups = Counter()
    memory_to_group = {}
    
    for i, memory in enumerate(memories):
        text = memory.get("text", "").strip()
        if not text:
            continue
        
        # Create a simple key for grouping similar memories
        key = normalize_text_for_grouping(text)
        text_groups[key] += 1
        memory_to_group[i] = key
    
    # Convert back to memory frequencies
    frequencies = {}
    for i, memory in enumerate(memories):
        if i in memory_to_group:
            key = memory_to_group[i]
            frequencies[f"memory_{i}"] = text_groups[key]
        else:
            frequencies[f"memory_{i}"] = 1
    
    return frequencies


def normalize_text_for_grouping(text: str, max_chars: int = 50) -> str:
    """Normalize text for frequency grouping."""
    # Remove common prefixes and punctuation
    text = text.lower().strip()
    
    # Remove action item prefixes
    if text.startswith("- [ ] ") or text.startswith("- [x] "):
        text = text[6:]
    elif text.startswith("- "):
        text = text[2:]
    
    # Take first N characters for grouping
    return text[:max_chars].strip()


def decay_scores_over_time(
    scored_memories: Dict[str, Any],
    config: Dict[str, Any],
    days_elapsed: int
) -> Dict[str, Any]:
    """Apply time-based decay to existing scores."""
    scoring_config = config.get("scoring", {})
    decay_half_life = scoring_config.get("decay_half_life_days", 14)
    
    if days_elapsed <= 0:
        return scored_memories
    
    # Calculate decay factor
    decay_factor = 0.5 ** (days_elapsed / decay_half_life)
    
    # Apply to all memories
    for memory_id, memory_data in scored_memories.items():
        if "score" in memory_data:
            memory_data["score"] *= decay_factor
            memory_data["last_decayed"] = datetime.now().isoformat()
    
    return scored_memories


def rank_memories_by_score(
    memories: List[Dict[str, Any]],
    scores: Dict[str, float],
    limit: Optional[int] = None
) -> List[Dict[str, Any]]:
    """Rank memories by their scores."""
    # Add scores to memories
    for i, memory in enumerate(memories):
        memory_id = memory.get("id", f"memory_{i}")
        memory["score"] = scores.get(memory_id, 0.0)
    
    # Sort by score (descending)
    ranked = sorted(memories, key=lambda m: m.get("score", 0.0), reverse=True)
    
    # Apply limit
    if limit:
        ranked = ranked[:limit]
    
    return ranked


def calculate_category_distribution(memories: List[Dict[str, Any]]) -> Dict[str, int]:
    """Calculate distribution of memories across categories."""
    categories = Counter()
    
    for memory in memories:
        category = memory.get("category", "unknown")
        categories[category] += 1
    
    return dict(categories)


def calculate_entity_scores(memories: List[Dict[str, Any]]) -> Dict[str, float]:
    """Calculate importance scores for entities mentioned across memories."""
    entity_counts = Counter()
    entity_contexts = {}
    
    # Count entity mentions and track contexts
    for memory in memories:
        entities = memory.get("entities", [])
        memory_score = memory.get("score", 1.0)
        
        for entity in entities:
            entity_counts[entity] += 1
            
            # Weight by memory score
            if entity not in entity_contexts:
                entity_contexts[entity] = []
            entity_contexts[entity].append(memory_score)
    
    # Calculate entity scores
    entity_scores = {}
    for entity, count in entity_counts.items():
        # Base score from frequency
        frequency_score = math.log(count + 1)
        
        # Weight by average context score
        context_scores = entity_contexts[entity]
        avg_context = sum(context_scores) / len(context_scores)
        
        entity_scores[entity] = frequency_score * avg_context
    
    return entity_scores


def filter_memories_by_score(
    memories: List[Dict[str, Any]],
    min_score: float = 0.1
) -> List[Dict[str, Any]]:
    """Filter memories below minimum score threshold."""
    return [m for m in memories if m.get("score", 0.0) >= min_score]


def boost_recent_memories(
    memories: List[Dict[str, Any]],
    boost_days: int = 7,
    boost_factor: float = 1.3
) -> List[Dict[str, Any]]:
    """Apply boost to recent memories."""
    cutoff_date = datetime.now() - timedelta(days=boost_days)
    
    for memory in memories:
        timestamp = parse_memory_timestamp(memory.get("timestamp"))
        if timestamp and timestamp > cutoff_date:
            current_score = memory.get("score", 1.0)
            memory["score"] = current_score * boost_factor
    
    return memories