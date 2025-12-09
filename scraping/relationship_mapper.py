"""
Relationship Mapper - Social graph analysis and relationship intelligence.

Features:
- Build and analyze social network graphs
- Identify influential users and key connectors
- Map interaction patterns and communities
- Find relationship paths between users
"""

import json
import logging
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple

try:
    import networkx as nx

    NETWORKX_AVAILABLE = True
except ImportError:
    NETWORKX_AVAILABLE = False
    logging.warning("NetworkX not available - limited graph functionality")

from pyrogram.types import Message

logger = logging.getLogger(__name__)


@dataclass
class Relationship:
    """Represents a relationship between two users."""

    user_id_1: int
    user_id_2: int
    strength: float = 0.0  # 0-1 relationship strength
    interactions: int = 0
    common_groups: int = 0
    mutual_friends: int = 0
    first_interaction: Optional[datetime] = None
    last_interaction: Optional[datetime] = None
    relationship_type: str = "unknown"  # friend, colleague, acquaintance, etc.


@dataclass
class CommunityCluster:
    """Represents a community or cluster of users."""

    cluster_id: int
    members: Set[int] = field(default_factory=set)
    density: float = 0.0
    avg_connections: float = 0.0
    central_members: List[int] = field(default_factory=list)
    topics: List[str] = field(default_factory=list)


class RelationshipMapper:
    """Social graph analysis and relationship mapping."""

    def __init__(self, db_path: str = "intelligence.db"):
        """Initialize relationship mapper.

        Args:
            db_path: Path to intelligence database
        """
        self.db_path = db_path
        self.graph = None
        if NETWORKX_AVAILABLE:
            self.graph = nx.Graph()
        self._connection_pool = None
        try:
            from database.connection_pool import get_pool

            self._connection_pool = get_pool(self.db_path)
        except Exception as exc:
            logger.debug(f"Connection pool unavailable for relationship mapper: {exc}")
        self._init_database()

    def _get_connection(self):
        """Return a DB connection from pool or direct sqlite."""
        if self._connection_pool:
            return self._connection_pool.get_connection()
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_database(self):
        """Initialize relationship tables."""
        conn = self._get_connection()
        cursor = conn.cursor()

        # Relationships table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS relationships (
                user_id_1 INTEGER,
                user_id_2 INTEGER,
                strength REAL DEFAULT 0.0,
                interactions INTEGER DEFAULT 0,
                common_groups INTEGER DEFAULT 0,
                mutual_friends INTEGER DEFAULT 0,
                first_interaction TIMESTAMP,
                last_interaction TIMESTAMP,
                relationship_type TEXT,
                PRIMARY KEY (user_id_1, user_id_2)
            )
        """
        )

        # Community clusters
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS community_clusters (
                cluster_id INTEGER PRIMARY KEY AUTOINCREMENT,
                density REAL,
                avg_connections REAL,
                topics TEXT,
                created_at TIMESTAMP,
                updated_at TIMESTAMP
            )
        """
        )

        # Cluster members
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS cluster_members (
                cluster_id INTEGER,
                user_id INTEGER,
                centrality REAL,
                PRIMARY KEY (cluster_id, user_id)
            )
        """
        )

        # Indexes
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_rel_strength ON relationships(strength DESC)"
        )
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_rel_user1 ON relationships(user_id_1)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_rel_user2 ON relationships(user_id_2)")

        conn.commit()
        conn.close()

    def add_relationship(
        self, user_id_1: int, user_id_2: int, interaction_type: str = "message", weight: float = 1.0
    ):
        """Add or update a relationship between two users.

        Args:
            user_id_1: First user ID
            user_id_2: Second user ID
            interaction_type: Type of interaction
            weight: Interaction weight
        """
        # Normalize order (smaller ID first)
        if user_id_1 > user_id_2:
            user_id_1, user_id_2 = user_id_2, user_id_1

        conn = self._get_connection()
        cursor = conn.cursor()

        # Check if relationship exists
        cursor.execute(
            """
            SELECT interactions, strength, first_interaction
            FROM relationships
            WHERE user_id_1 = ? AND user_id_2 = ?
        """,
            (user_id_1, user_id_2),
        )

        row = cursor.fetchone()
        now = datetime.now()

        if row:
            # Update existing
            new_interactions = row[0] + 1
            new_strength = min(1.0, row[1] + (weight * 0.05))  # Incremental strength increase
            cursor.execute(
                """
                UPDATE relationships
                SET interactions = ?, strength = ?, last_interaction = ?
                WHERE user_id_1 = ? AND user_id_2 = ?
            """,
                (new_interactions, new_strength, now, user_id_1, user_id_2),
            )
        else:
            # Create new
            cursor.execute(
                """
                INSERT INTO relationships (
                    user_id_1, user_id_2, strength, interactions,
                    first_interaction, last_interaction, relationship_type
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
                (user_id_1, user_id_2, weight * 0.05, 1, now, now, "acquaintance"),
            )

        conn.commit()
        conn.close()

        # Update graph
        if NETWORKX_AVAILABLE and self.graph:
            if row:
                self.graph.add_edge(user_id_1, user_id_2, weight=min(1.0, row[1] + (weight * 0.05)))
            else:
                self.graph.add_edge(user_id_1, user_id_2, weight=weight * 0.05)

    def get_relationship(self, user_id_1: int, user_id_2: int) -> Optional[Relationship]:
        """Get relationship between two users."""
        if user_id_1 > user_id_2:
            user_id_1, user_id_2 = user_id_2, user_id_1

        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT * FROM relationships WHERE user_id_1 = ? AND user_id_2 = ?
        """,
            (user_id_1, user_id_2),
        )

        row = cursor.fetchone()
        conn.close()

        if not row:
            return None

        return Relationship(
            user_id_1=row[0],
            user_id_2=row[1],
            strength=row[2],
            interactions=row[3],
            common_groups=row[4],
            mutual_friends=row[5],
            first_interaction=datetime.fromisoformat(row[6]) if row[6] else None,
            last_interaction=datetime.fromisoformat(row[7]) if row[7] else None,
            relationship_type=row[8],
        )

    def find_shortest_path(self, user_id_1: int, user_id_2: int) -> Optional[List[int]]:
        """Find shortest relationship path between two users.

        Returns:
            List of user IDs representing the path, or None if no path exists
        """
        if not NETWORKX_AVAILABLE or not self.graph:
            logger.warning("NetworkX required for path finding")
            return None

        try:
            path = nx.shortest_path(self.graph, user_id_1, user_id_2)
            return path
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return None

    def get_mutual_connections(self, user_id_1: int, user_id_2: int) -> List[int]:
        """Get mutual connections between two users."""
        if not NETWORKX_AVAILABLE or not self.graph:
            return []

        try:
            neighbors_1 = set(self.graph.neighbors(user_id_1))
            neighbors_2 = set(self.graph.neighbors(user_id_2))
            return list(neighbors_1.intersection(neighbors_2))
        except nx.NodeNotFound:
            return []

    def calculate_user_centrality(self, user_id: int) -> Dict[str, float]:
        """Calculate various centrality metrics for a user.

        Returns:
            Dictionary with centrality scores
        """
        if not NETWORKX_AVAILABLE or not self.graph or user_id not in self.graph:
            return {}

        try:
            return {
                "degree": nx.degree_centrality(self.graph)[user_id],
                "betweenness": nx.betweenness_centrality(self.graph)[user_id],
                "closeness": nx.closeness_centrality(self.graph)[user_id],
                "eigenvector": nx.eigenvector_centrality(self.graph, max_iter=100)[user_id],
            }
        except Exception as e:
            logger.error(f"Error calculating centrality for {user_id}: {e}")
            return {}

    def identify_influencers(self, top_n: int = 20) -> List[Tuple[int, float]]:
        """Identify most influential users in the network.

        Returns:
            List of (user_id, influence_score) tuples
        """
        if not NETWORKX_AVAILABLE or not self.graph:
            return []

        try:
            # Use PageRank as influence metric
            pagerank = nx.pagerank(self.graph)
            sorted_users = sorted(pagerank.items(), key=lambda x: x[1], reverse=True)
            return sorted_users[:top_n]
        except Exception as e:
            logger.error(f"Error identifying influencers: {e}")
            return []

    def detect_communities(self, min_size: int = 5) -> List[CommunityCluster]:
        """Detect community clusters in the network.

        Args:
            min_size: Minimum cluster size

        Returns:
            List of CommunityCluster objects
        """
        if not NETWORKX_AVAILABLE or not self.graph:
            return []

        try:
            # Use Louvain community detection
            from networkx.algorithms import community

            communities = community.greedy_modularity_communities(self.graph)

            clusters = []
            for i, comm in enumerate(communities):
                if len(comm) >= min_size:
                    cluster = CommunityCluster(cluster_id=i, members=comm)

                    # Calculate metrics
                    subgraph = self.graph.subgraph(comm)
                    cluster.density = nx.density(subgraph)
                    cluster.avg_connections = sum(dict(subgraph.degree()).values()) / len(comm)

                    # Find central members
                    centrality = nx.degree_centrality(subgraph)
                    cluster.central_members = sorted(centrality, key=centrality.get, reverse=True)[
                        :5
                    ]

                    clusters.append(cluster)

                    # Save to database
                    self._save_cluster(cluster)

            logger.info(f"Detected {len(clusters)} communities")
            return clusters

        except Exception as e:
            logger.error(f"Error detecting communities: {e}")
            return []

    def _save_cluster(self, cluster: CommunityCluster):
        """Save cluster to database."""
        conn = self._get_connection()
        cursor = conn.cursor()

        now = datetime.now()
        cursor.execute(
            """
            INSERT INTO community_clusters (cluster_id, density, avg_connections, topics, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(cluster_id) DO UPDATE SET
                density = excluded.density,
                avg_connections = excluded.avg_connections,
                updated_at = excluded.updated_at
        """,
            (
                cluster.cluster_id,
                cluster.density,
                cluster.avg_connections,
                json.dumps(cluster.topics),
                now,
                now,
            ),
        )

        # Save members
        for member in cluster.members:
            centrality = self.calculate_user_centrality(member).get("degree", 0.0)
            cursor.execute(
                """
                INSERT OR REPLACE INTO cluster_members (cluster_id, user_id, centrality)
                VALUES (?, ?, ?)
            """,
                (cluster.cluster_id, member, centrality),
            )

        conn.commit()
        conn.close()

    def find_bridge_users(self, top_n: int = 10) -> List[Tuple[int, float]]:
        """Find users who bridge different communities.

        Returns:
            List of (user_id, betweenness_score) tuples
        """
        if not NETWORKX_AVAILABLE or not self.graph:
            return []

        try:
            betweenness = nx.betweenness_centrality(self.graph)
            sorted_users = sorted(betweenness.items(), key=lambda x: x[1], reverse=True)
            return sorted_users[:top_n]
        except Exception as e:
            logger.error(f"Error finding bridge users: {e}")
            return []

    def get_user_network_stats(self, user_id: int) -> Dict[str, Any]:
        """Get network statistics for a user."""
        if not NETWORKX_AVAILABLE or not self.graph or user_id not in self.graph:
            return {}

        try:
            neighbors = list(self.graph.neighbors(user_id))

            # Calculate clustering coefficient (how interconnected are neighbors)
            clustering = nx.clustering(self.graph, user_id)

            # Get centrality metrics
            centrality = self.calculate_user_centrality(user_id)

            return {
                "connections": len(neighbors),
                "clustering_coefficient": clustering,
                "centrality_metrics": centrality,
                "neighbors": neighbors[:10],  # Top 10 connections
            }
        except Exception as e:
            logger.error(f"Error getting network stats for {user_id}: {e}")
            return {}

    def rebuild_graph_from_db(self):
        """Rebuild in-memory graph from database."""
        if not NETWORKX_AVAILABLE:
            return

        self.graph = nx.Graph()

        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT user_id_1, user_id_2, strength FROM relationships")

        for row in cursor.fetchall():
            self.graph.add_edge(row[0], row[1], weight=row[2])

        conn.close()
        logger.info(
            f"Rebuilt graph with {self.graph.number_of_nodes()} nodes and {self.graph.number_of_edges()} edges"
        )

    def analyze_message_for_relationships(self, message: Message):
        """Analyze a message to extract relationship information.

        Args:
            message: Pyrogram Message object
        """
        if not message.from_user:
            return

        sender_id = message.from_user.id

        # If it's a reply, it's an interaction
        if message.reply_to_message and message.reply_to_message.from_user:
            target_id = message.reply_to_message.from_user.id
            self.add_relationship(sender_id, target_id, "reply", weight=2.0)

        # Check for mentions
        if message.entities:
            for entity in message.entities:
                if entity.type == "mention" or entity.type == "text_mention":
                    if hasattr(entity, "user") and entity.user:
                        target_id = entity.user.id
                        self.add_relationship(sender_id, target_id, "mention", weight=1.5)

        # Group message interaction
        if message.chat and message.chat.type in ["group", "supergroup"]:
            # This is a general group interaction
            pass

    def export_graph_data(self, format: str = "json") -> Optional[str]:
        """Export graph data for visualization.

        Args:
            format: Export format (json, gexf, graphml)

        Returns:
            Exported data as string
        """
        if not NETWORKX_AVAILABLE or not self.graph:
            return None

        try:
            if format == "json":
                from networkx.readwrite import json_graph

                data = json_graph.node_link_data(self.graph)
                return json.dumps(data, indent=2)
            elif format == "gexf":
                import io

                buffer = io.StringIO()
                nx.write_gexf(self.graph, buffer)
                return buffer.getvalue()
            elif format == "graphml":
                import io

                buffer = io.StringIO()
                nx.write_graphml(self.graph, buffer)
                return buffer.getvalue()
            else:
                logger.error(f"Unsupported export format: {format}")
                return None
        except Exception as e:
            logger.error(f"Error exporting graph: {e}")
            return None

    def get_relationship_stats(self) -> Dict[str, Any]:
        """Get overall relationship statistics."""
        conn = self._get_connection()
        cursor = conn.cursor()

        # Total relationships
        cursor.execute("SELECT COUNT(*) FROM relationships")
        total = cursor.fetchone()[0]

        # Average strength
        cursor.execute("SELECT AVG(strength) FROM relationships")
        avg_strength = cursor.fetchone()[0] or 0.0

        # Relationship distribution by strength
        cursor.execute(
            """
            SELECT
                CASE
                    WHEN strength < 0.2 THEN 'weak'
                    WHEN strength < 0.5 THEN 'moderate'
                    WHEN strength < 0.8 THEN 'strong'
                    ELSE 'very_strong'
                END as category,
                COUNT(*) as count
            FROM relationships
            GROUP BY category
        """
        )
        distribution = dict(cursor.fetchall())

        conn.close()

        stats = {
            "total_relationships": total,
            "average_strength": avg_strength,
            "distribution": distribution,
        }

        if NETWORKX_AVAILABLE and self.graph:
            stats["network_density"] = nx.density(self.graph)
            stats["total_nodes"] = self.graph.number_of_nodes()
            stats["total_edges"] = self.graph.number_of_edges()

        return stats


# Utility functions
def analyze_group_relationships(mapper: RelationshipMapper, messages: List[Message]):
    """Analyze relationships from group messages.

    Args:
        mapper: RelationshipMapper instance
        messages: List of messages to analyze
    """
    for message in messages:
        mapper.analyze_message_for_relationships(message)
