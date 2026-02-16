#!/usr/bin/env python3
"""
Entity Graph for Second Brain v2

Build and query entity relationship graphs from extracted memories.
"""

import argparse
import json
import sys
from collections import defaultdict, Counter
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Set, Tuple

# Add utils to path
sys.path.append(str(Path(__file__).parent))

from utils.memory_io import (
    load_config, get_memory_files, read_memory_file,
    load_memory_index
)


class EntityGraph:
    """Represents entity relationships extracted from memories."""
    
    def __init__(self):
        """Initialize empty graph."""
        self.nodes = {}  # entity_id -> node_data
        self.edges = defaultdict(list)  # entity_id -> [connected_entity_ids]
        self.relationships = []  # List of relationship records
        self.metadata = {
            'created_at': datetime.now().isoformat(),
            'total_memories_processed': 0,
            'total_files_processed': 0
        }
    
    def add_entity(self, entity: str, entity_type: str, context: str = "", source_file: str = "") -> str:
        """Add an entity to the graph."""
        entity_id = self._normalize_entity_id(entity)
        
        if entity_id not in self.nodes:
            self.nodes[entity_id] = {
                'id': entity_id,
                'name': entity,
                'type': entity_type,
                'mentions': 0,
                'contexts': [],
                'source_files': set(),
                'first_seen': datetime.now().isoformat(),
                'last_seen': datetime.now().isoformat()
            }
        
        # Update node data
        node = self.nodes[entity_id]
        node['mentions'] += 1
        node['last_seen'] = datetime.now().isoformat()
        
        if context and context not in node['contexts']:
            node['contexts'].append(context)
        
        if source_file:
            node['source_files'].add(source_file)
        
        return entity_id
    
    def add_relationship(self, entity1: str, entity2: str, relationship_type: str, 
                        context: str = "", source_file: str = "") -> None:
        """Add a relationship between two entities."""
        entity1_id = self._normalize_entity_id(entity1)
        entity2_id = self._normalize_entity_id(entity2)
        
        if entity1_id == entity2_id:
            return  # No self-loops
        
        # Add entities if they don't exist
        if entity1_id not in self.nodes:
            self.add_entity(entity1, "unknown", context, source_file)
        if entity2_id not in self.nodes:
            self.add_entity(entity2, "unknown", context, source_file)
        
        # Add bidirectional edges
        if entity2_id not in self.edges[entity1_id]:
            self.edges[entity1_id].append(entity2_id)
        if entity1_id not in self.edges[entity2_id]:
            self.edges[entity2_id].append(entity1_id)
        
        # Record relationship
        self.relationships.append({
            'entity1': entity1_id,
            'entity2': entity2_id,
            'type': relationship_type,
            'context': context,
            'source_file': source_file,
            'timestamp': datetime.now().isoformat()
        })
    
    def _normalize_entity_id(self, entity: str) -> str:
        """Normalize entity name to ID."""
        return entity.lower().strip().replace(' ', '_').replace('-', '_')
    
    def get_connected_entities(self, entity: str, max_depth: int = 2) -> List[Dict[str, Any]]:
        """Get entities connected to the given entity."""
        entity_id = self._normalize_entity_id(entity)
        
        if entity_id not in self.nodes:
            return []
        
        visited = set()
        to_visit = [(entity_id, 0)]  # (entity_id, depth)
        connected = []
        
        while to_visit:
            current_id, depth = to_visit.pop(0)
            
            if current_id in visited or depth > max_depth:
                continue
            
            visited.add(current_id)
            
            if current_id != entity_id:  # Don't include the query entity itself
                node = self.nodes[current_id].copy()
                node['source_files'] = list(node['source_files'])  # Convert set to list for JSON
                node['connection_depth'] = depth
                connected.append(node)
            
            # Add connected entities
            if depth < max_depth:
                for neighbor_id in self.edges.get(current_id, []):
                    if neighbor_id not in visited:
                        to_visit.append((neighbor_id, depth + 1))
        
        # Sort by mentions (most mentioned first)
        connected.sort(key=lambda x: x.get('mentions', 0), reverse=True)
        
        return connected
    
    def get_entity_stats(self) -> Dict[str, Any]:
        """Get statistics about the entity graph."""
        if not self.nodes:
            return {'total_entities': 0, 'total_relationships': 0}
        
        # Count by type
        type_counts = Counter(node.get('type', 'unknown') for node in self.nodes.values())
        
        # Connection statistics
        connection_counts = [len(connections) for connections in self.edges.values()]
        avg_connections = sum(connection_counts) / len(connection_counts) if connection_counts else 0
        
        # Most mentioned entities
        most_mentioned = sorted(
            self.nodes.values(),
            key=lambda x: x.get('mentions', 0),
            reverse=True
        )[:10]
        
        # Most connected entities
        most_connected = sorted(
            [(entity_id, len(connections)) for entity_id, connections in self.edges.items()],
            key=lambda x: x[1],
            reverse=True
        )[:10]
        
        return {
            'total_entities': len(self.nodes),
            'total_relationships': len(self.relationships),
            'entities_by_type': dict(type_counts),
            'avg_connections_per_entity': avg_connections,
            'most_mentioned': [
                {'name': e.get('name', ''), 'mentions': e.get('mentions', 0)}
                for e in most_mentioned
            ],
            'most_connected': [
                {'name': self.nodes.get(entity_id, {}).get('name', entity_id), 'connections': count}
                for entity_id, count in most_connected
            ]
        }
    
    def export_json(self) -> Dict[str, Any]:
        """Export graph as JSON."""
        # Convert sets to lists for JSON serialization
        nodes_json = {}
        for entity_id, node in self.nodes.items():
            node_copy = node.copy()
            node_copy['source_files'] = list(node_copy['source_files'])
            nodes_json[entity_id] = node_copy
        
        return {
            'metadata': self.metadata,
            'nodes': nodes_json,
            'edges': dict(self.edges),
            'relationships': self.relationships,
            'stats': self.get_entity_stats()
        }
    
    def load_from_json(self, data: Dict[str, Any]) -> None:
        """Load graph from JSON data."""
        self.metadata = data.get('metadata', {})
        
        # Load nodes
        nodes_data = data.get('nodes', {})
        for entity_id, node in nodes_data.items():
            node['source_files'] = set(node.get('source_files', []))
            self.nodes[entity_id] = node
        
        # Load edges
        edges_data = data.get('edges', {})
        for entity_id, connections in edges_data.items():
            self.edges[entity_id] = connections
        
        # Load relationships
        self.relationships = data.get('relationships', [])


def extract_entities_from_memory_file(file_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract entities from a memory file."""
    entities = []
    sections = file_data.get('sections', {})
    file_path = file_data.get('path', '')
    
    # Extract people from people_mentioned section
    people_items = sections.get('people_mentioned', [])
    for item in people_items:
        # Parse "**Name**: context" format
        if item.startswith('**') and '**:' in item:
            parts = item.split('**:', 1)
            name = parts[0].strip('*').strip()
            context = parts[1].strip() if len(parts) > 1 else ""
            
            entities.append({
                'name': name,
                'type': 'person',
                'context': context,
                'source_file': file_path,
                'section': 'people_mentioned'
            })
    
    # Extract projects from key_topics_&_projects
    projects_items = sections.get('key_topics_&_projects', []) + sections.get('projects_&_tools', [])
    for item in projects_items:
        # Look for project names (often capitalized or hyphenated)
        if ':' in item:
            project_name = item.split(':', 1)[0].strip()
            context = item.split(':', 1)[1].strip() if len(item.split(':', 1)) > 1 else ""
        else:
            project_name = item.strip()
            context = ""
        
        # Filter out very generic terms
        if len(project_name) > 2 and not project_name.lower() in ['the', 'and', 'for', 'with']:
            entities.append({
                'name': project_name,
                'type': 'project',
                'context': context,
                'source_file': file_path,
                'section': 'projects'
            })
    
    # Extract technologies from technical_details
    tech_items = sections.get('technical_details', [])
    for item in tech_items:
        # Look for technology keywords
        tech_keywords = [
            'python', 'javascript', 'typescript', 'java', 'rust', 'go', 'c++',
            'react', 'vue', 'angular', 'django', 'flask', 'fastapi', 'express',
            'docker', 'kubernetes', 'aws', 'azure', 'gcp', 'github', 'git',
            'openai', 'anthropic', 'claude', 'gpt', 'api', 'rest', 'graphql',
            'postgres', 'mysql', 'redis', 'mongodb', 'sqlite', 'openclaw'
        ]
        
        item_lower = item.lower()
        for tech in tech_keywords:
            if tech in item_lower:
                entities.append({
                    'name': tech,
                    'type': 'technology',
                    'context': item,
                    'source_file': file_path,
                    'section': 'technical_details'
                })
                break  # Only add one tech per item
    
    # Extract decisions as entities
    decisions = sections.get('decisions_made', [])
    for i, decision in enumerate(decisions):
        decision_id = f"decision_{i+1}"
        entities.append({
            'name': decision_id,
            'type': 'decision',
            'context': decision,
            'source_file': file_path,
            'section': 'decisions_made'
        })
    
    return entities


def find_co_occurrences(entities: List[Dict[str, Any]]) -> List[Tuple[str, str, str]]:
    """Find entities that co-occur in the same file/context."""
    relationships = []
    
    # Group entities by source file
    by_file = defaultdict(list)
    for entity in entities:
        by_file[entity['source_file']].append(entity)
    
    # Find relationships within each file
    for file_path, file_entities in by_file.items():
        for i, entity1 in enumerate(file_entities):
            for entity2 in file_entities[i+1:]:
                # Don't connect entities of the same type unless they're people
                if (entity1['type'] != entity2['type'] or 
                    (entity1['type'] == 'person' and entity2['type'] == 'person')):
                    
                    relationship_type = f"co_occurred_in_{Path(file_path).stem}"
                    relationships.append((entity1['name'], entity2['name'], relationship_type))
    
    return relationships


def build_entity_graph(config: Dict[str, Any]) -> EntityGraph:
    """Build entity graph from all memory files."""
    memory_dir = Path(config['memory_dir']).expanduser()
    memory_files = get_memory_files(memory_dir)
    
    graph = EntityGraph()
    all_entities = []
    
    # Process each memory file
    for file_path in memory_files:
        try:
            file_data = read_memory_file(file_path)
            entities = extract_entities_from_memory_file(file_data)
            
            # Add entities to graph
            for entity in entities:
                graph.add_entity(
                    entity['name'],
                    entity['type'],
                    entity['context'],
                    entity['source_file']
                )
            
            all_entities.extend(entities)
            graph.metadata['total_files_processed'] += 1
            
        except Exception as e:
            print(f"Warning: Failed to process {file_path}: {e}", file=sys.stderr)
            continue
    
    # Find relationships
    relationships = find_co_occurrences(all_entities)
    
    for entity1, entity2, rel_type in relationships:
        graph.add_relationship(entity1, entity2, rel_type)
    
    graph.metadata['total_memories_processed'] = len(all_entities)
    graph.metadata['built_at'] = datetime.now().isoformat()
    
    return graph


def save_entity_graph(graph: EntityGraph, file_path: Path) -> None:
    """Save entity graph to file."""
    graph_data = graph.export_json()
    
    with open(file_path, 'w') as f:
        json.dump(graph_data, f, indent=2, default=str)


def load_entity_graph(file_path: Path) -> EntityGraph:
    """Load entity graph from file."""
    if not file_path.exists():
        return EntityGraph()
    
    try:
        with open(file_path, 'r') as f:
            data = json.load(f)
        
        graph = EntityGraph()
        graph.load_from_json(data)
        return graph
    
    except (json.JSONDecodeError, KeyError) as e:
        print(f"Warning: Failed to load graph from {file_path}: {e}", file=sys.stderr)
        return EntityGraph()


def format_graph_stats(stats: Dict[str, Any]) -> str:
    """Format graph statistics for display."""
    lines = []
    
    lines.append("🕸️  Entity Graph Statistics")
    lines.append("=" * 40)
    lines.append(f"Total entities: {stats.get('total_entities', 0):,}")
    lines.append(f"Total relationships: {stats.get('total_relationships', 0):,}")
    lines.append(f"Avg connections per entity: {stats.get('avg_connections_per_entity', 0):.1f}")
    lines.append("")
    
    # Entities by type
    entities_by_type = stats.get('entities_by_type', {})
    if entities_by_type:
        lines.append("Entities by type:")
        for entity_type, count in sorted(entities_by_type.items(), key=lambda x: x[1], reverse=True):
            lines.append(f"  {entity_type}: {count}")
        lines.append("")
    
    # Most mentioned entities
    most_mentioned = stats.get('most_mentioned', [])
    if most_mentioned:
        lines.append("Most mentioned entities:")
        for entity in most_mentioned[:10]:
            lines.append(f"  {entity['name']}: {entity['mentions']} mentions")
        lines.append("")
    
    # Most connected entities
    most_connected = stats.get('most_connected', [])
    if most_connected:
        lines.append("Most connected entities:")
        for entity in most_connected[:10]:
            lines.append(f"  {entity['name']}: {entity['connections']} connections")
        lines.append("")
    
    return "\n".join(lines)


def format_entity_connections(entity_name: str, connections: List[Dict[str, Any]]) -> str:
    """Format entity connections for display."""
    if not connections:
        return f"No connections found for '{entity_name}'"
    
    lines = []
    lines.append(f"🔗 Connections for '{entity_name}' ({len(connections)} found)")
    lines.append("=" * 50)
    
    # Group by type and depth
    by_type = defaultdict(list)
    for conn in connections:
        entity_type = conn.get('type', 'unknown')
        by_type[entity_type].append(conn)
    
    for entity_type, entities in by_type.items():
        lines.append(f"\n{entity_type.title()}s:")
        
        # Sort by mentions and depth
        entities.sort(key=lambda x: (x.get('connection_depth', 0), -x.get('mentions', 0)))
        
        for entity in entities[:10]:  # Limit to top 10 per type
            depth = entity.get('connection_depth', 0)
            mentions = entity.get('mentions', 0)
            name = entity.get('name', 'Unknown')
            
            depth_indicator = "  " + "→ " * depth
            lines.append(f"{depth_indicator}{name} ({mentions} mentions)")
            
            # Show context if available
            contexts = entity.get('contexts', [])
            if contexts:
                context = contexts[0][:100] + "..." if len(contexts[0]) > 100 else contexts[0]
                lines.append(f"    \"{context}\"")
    
    return "\n".join(lines)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Build and query entity relationship graphs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 graph.py --build                     # Build entity graph
  python3 graph.py --query "DpuDebugAgent"    # Query connections
  python3 graph.py --stats                    # Show graph statistics
  python3 graph.py --export graph.json        # Export graph data
        """
    )
    
    parser.add_argument(
        '--config',
        type=Path,
        help='Path to configuration file'
    )
    
    parser.add_argument(
        '--build',
        action='store_true',
        help='Build entity graph from memory files'
    )
    
    parser.add_argument(
        '--query',
        help='Query connections for an entity'
    )
    
    parser.add_argument(
        '--stats',
        action='store_true',
        help='Show graph statistics'
    )
    
    parser.add_argument(
        '--export',
        type=Path,
        help='Export graph data to JSON file'
    )
    
    parser.add_argument(
        '--import',
        type=Path,
        dest='import_file',
        help='Import graph data from JSON file'
    )
    
    parser.add_argument(
        '--max-depth',
        type=int,
        default=2,
        help='Maximum depth for connection queries (default: 2)'
    )
    
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Show verbose output'
    )
    
    args = parser.parse_args()
    
    try:
        # Load configuration
        config = load_config(args.config)
        memory_dir = Path(config['memory_dir']).expanduser()
        
        # Default graph file location
        graph_file = memory_dir / ".entity-graph.json"
        
        # Import graph if specified
        if args.import_file:
            graph = load_entity_graph(args.import_file)
            save_entity_graph(graph, graph_file)
            print(f"Graph imported from {args.import_file}")
            return
        
        # Build graph if requested or if it doesn't exist
        if args.build or not graph_file.exists():
            if args.verbose:
                print("Building entity graph from memory files...")
            
            graph = build_entity_graph(config)
            save_entity_graph(graph, graph_file)
            
            print(f"✅ Entity graph built with {len(graph.nodes)} entities and {len(graph.relationships)} relationships")
            print(f"Graph saved to: {graph_file}")
        else:
            # Load existing graph
            graph = load_entity_graph(graph_file)
        
        # Handle query
        if args.query:
            connections = graph.get_connected_entities(args.query, args.max_depth)
            output = format_entity_connections(args.query, connections)
            print(output)
        
        # Handle stats
        elif args.stats:
            stats = graph.get_entity_stats()
            output = format_graph_stats(stats)
            print(output)
        
        # Handle export
        elif args.export:
            graph_data = graph.export_json()
            with open(args.export, 'w') as f:
                json.dump(graph_data, f, indent=2, default=str)
            print(f"Graph exported to: {args.export}")
        
        # Default: show brief stats
        elif not args.build:
            stats = graph.get_entity_stats()
            print(f"🕸️  Entity Graph: {stats.get('total_entities', 0)} entities, {stats.get('total_relationships', 0)} relationships")
            print(f"Last built: {graph.metadata.get('built_at', 'Unknown')}")
            print("\nUse --stats for detailed statistics or --query <entity> to explore connections")
        
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()