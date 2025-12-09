"""
Network Analytics - Social graph analysis and network intelligence.

Features:
- Build and analyze social network graphs
- Identify influential users
- Detect communities
- Calculate centrality metrics
- Find key connectors
"""

import logging
import sqlite3
import json
from typing import List, Dict, Optional, Tuple, Set
from datetime import datetime
from dataclasses import dataclass, field
from collections import defaultdict
from contextlib import contextmanager

try:
    import networkx as nx

    NETWORKX_AVAILABLE = True
except ImportError:
    NETWORKX_AVAILABLE = False
    logging.warning("NetworkX not available - graph analysis will be limited")

logger = logging.getLogger(__name__)


@dataclass
class NetworkNode:
    """Node in the social network."""

    user_id: int
    username: Optional[str] = None
    connections: int = 0
    centrality_score: float = 0.0
    influence_score: float = 0.0
    cluster_id: Optional[int] = None


@dataclass
class NetworkCluster:
    """Community cluster in network."""

    cluster_id: int
    member_count: int
    density: float
    top_influencers: List[int] = field(default_factory=list)
    common_topics: List[str] = field(default_factory=list)


class NetworkAnalytics:
    """Social network analysis and graph analytics."""

    def __init__(self, db_path: str = "network.db"):
        """Initialize."""
        self.db_path = db_path
        self._connection_pool = None
        try:
            from database.connection_pool import get_pool

            self._connection_pool = get_pool(self.db_path)
        except Exception as e:
            logger.debug(f"Error initializing network analytics database (non-critical): {e}")
            pass
        self._init_database()

    def _get_connection(self):
        if self._connection_pool:
            return self._connection_pool.get_connection()
        else:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            return conn

    @contextmanager
    def _connection_context(self):
        """Context manager for DB operations."""
        conn_manager = self._get_connection()
        if hasattr(conn_manager, "__enter__"):
            with conn_manager as conn:
                yield conn
        else:
            try:
                yield conn_manager
            finally:
                try:
                    conn_manager.close()
                except Exception:
                    pass

        # Initialize graph
        if NETWORKX_AVAILABLE:
            self.graph = nx.Graph()
        else:
            self.graph = None

    def _init_database(self):
        """Initialize network database."""
        with self._connection_context() as conn:
            cursor = conn.cursor()

            # Network nodes
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS network_nodes (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    connections INTEGER DEFAULT 0,
                    centrality_score REAL DEFAULT 0.0,
                    influence_score REAL DEFAULT 0.0,
                    cluster_id INTEGER,
                    last_updated TIMESTAMP
                )
            """
            )

            # Network edges (connections)
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS network_edges (
                    user_id_1 INTEGER,
                    user_id_2 INTEGER,
                    strength REAL DEFAULT 1.0,
                    interaction_count INTEGER DEFAULT 1,
                    last_interaction TIMESTAMP,
                    PRIMARY KEY (user_id_1, user_id_2)
                )
            """
            )

            # Clusters/communities
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS network_clusters (
                    cluster_id INTEGER PRIMARY KEY,
                    member_count INTEGER,
                    density REAL,
                    top_influencers TEXT,
                    common_topics TEXT,
                    created_at TIMESTAMP,
                    last_updated TIMESTAMP
                )
            """
            )

            # Network metrics
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS network_metrics (
                    metric_name TEXT PRIMARY KEY,
                    metric_value REAL,
                    calculated_at TIMESTAMP
                )
            """
            )

            conn.commit()
        logger.info("Network analytics database initialized")

    def add_connection(self, user_id_1: int, user_id_2: int, strength: float = 1.0):
        """Add or update a connection between two users.

        Args:
            user_id_1: First user ID
            user_id_2: Second user ID
            strength: Connection strength (0-1)
        """
        # Normalize order
        if user_id_1 > user_id_2:
            user_id_1, user_id_2 = user_id_2, user_id_1

        conn = self._get_connection()
        cursor = conn.cursor()

        # Check if exists
        cursor.execute(
            """
            SELECT interaction_count FROM network_edges
            WHERE user_id_1 = ? AND user_id_2 = ?
        """,
            (user_id_1, user_id_2),
        )
        row = cursor.fetchone()

        if row:
            # Update existing
            new_count = row[0] + 1
            new_strength = min(1.0, strength + (new_count * 0.01))
            cursor.execute(
                """
                UPDATE network_edges
                SET strength = ?, interaction_count = ?, last_interaction = ?
                WHERE user_id_1 = ? AND user_id_2 = ?
            """,
                (new_strength, new_count, datetime.now(), user_id_1, user_id_2),
            )
        else:
            # Insert new
            cursor.execute(
                """
                INSERT INTO network_edges
                (user_id_1, user_id_2, strength, interaction_count, last_interaction)
                VALUES (?, ?, ?, 1, ?)
            """,
                (user_id_1, user_id_2, strength, datetime.now()),
            )

        conn.commit()
        conn.close()

        # Update graph if NetworkX available
        if NETWORKX_AVAILABLE and self.graph is not None:
            self.graph.add_edge(user_id_1, user_id_2, weight=strength)

        # Update node connection counts
        self._update_node_connections(user_id_1)
        self._update_node_connections(user_id_2)

    def _update_node_connections(self, user_id: int):
        """Update connection count for a node."""
        conn = self._get_connection()
        cursor = conn.cursor()

        # Count connections
        cursor.execute(
            """
            SELECT COUNT(*) FROM network_edges
            WHERE user_id_1 = ? OR user_id_2 = ?
        """,
            (user_id, user_id),
        )
        count = cursor.fetchone()[0]

        # Update node
        cursor.execute(
            """
            INSERT INTO network_nodes (user_id, connections, last_updated)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                connections = excluded.connections,
                last_updated = excluded.last_updated
        """,
            (user_id, count, datetime.now()),
        )

        conn.commit()
        conn.close()

    def calculate_influence_scores(self):
        """Calculate influence scores for all nodes using PageRank."""
        if not NETWORKX_AVAILABLE or not self.graph:
            logger.warning("NetworkX required for influence calculation")
            return

        try:
            # Calculate PageRank
            pagerank = nx.pagerank(self.graph)

            # Save to database
            conn = self._get_connection()
            cursor = conn.cursor()

            for user_id, score in pagerank.items():
                cursor.execute(
                    """
                    UPDATE network_nodes
                    SET influence_score = ?, last_updated = ?
                    WHERE user_id = ?
                """,
                    (score, datetime.now(), user_id),
                )

            conn.commit()
            conn.close()

            logger.info(f"Calculated influence scores for {len(pagerank)} nodes")

        except Exception as e:
            logger.error(f"Error calculating influence scores: {e}")

    def get_top_influencers(self, limit: int = 20) -> List[NetworkNode]:
        """Get top influential users in the network.

        Args:
            limit: Number of influencers to return

        Returns:
            List of NetworkNode objects
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT * FROM network_nodes
            ORDER BY influence_score DESC
            LIMIT ?
        """,
            (limit,),
        )

        nodes = []
        for row in cursor.fetchall():
            node = NetworkNode(
                user_id=row[0],
                username=row[1],
                connections=row[2],
                centrality_score=row[3],
                influence_score=row[4],
                cluster_id=row[5],
            )
            nodes.append(node)

        conn.close()
        return nodes

    def detect_communities(self) -> List[NetworkCluster]:
        """Detect communities/clusters in the network.

        Returns:
            List of NetworkCluster objects
        """
        if not NETWORKX_AVAILABLE or not self.graph:
            logger.warning("NetworkX required for community detection")
            return []

        try:
            from networkx.algorithms import community

            # Detect communities
            communities = community.greedy_modularity_communities(self.graph)

            clusters = []
            for i, comm in enumerate(communities):
                if len(comm) >= 5:  # Minimum size
                    # Calculate density
                    subgraph = self.graph.subgraph(comm)
                    density = nx.density(subgraph)

                    # Get top influencers
                    pagerank = nx.pagerank(subgraph)
                    top_influencers = sorted(pagerank, key=pagerank.get, reverse=True)[:5]

                    cluster = NetworkCluster(
                        cluster_id=i,
                        member_count=len(comm),
                        density=density,
                        top_influencers=top_influencers,
                    )
                    clusters.append(cluster)

                    # Save to database
                    self._save_cluster(cluster, list(comm))

            logger.info(f"Detected {len(clusters)} communities")
            return clusters

        except Exception as e:
            logger.error(f"Error detecting communities: {e}")
            return []

    def _save_cluster(self, cluster: NetworkCluster, members: List[int]):
        """Save cluster to database."""
        conn = self._get_connection()
        cursor = conn.cursor()

        # Save cluster
        cursor.execute(
            """
            INSERT OR REPLACE INTO network_clusters
            (cluster_id, member_count, density, top_influencers, created_at, last_updated)
            VALUES (?, ?, ?, ?, ?, ?)
        """,
            (
                cluster.cluster_id,
                cluster.member_count,
                cluster.density,
                json.dumps(cluster.top_influencers),
                datetime.now(),
                datetime.now(),
            ),
        )

        # Update node cluster assignments
        for user_id in members:
            cursor.execute(
                """
                UPDATE network_nodes SET cluster_id = ? WHERE user_id = ?
            """,
                (cluster.cluster_id, user_id),
            )

        conn.commit()
        conn.close()

    def find_bridges(self, top_n: int = 10) -> List[Tuple[int, float]]:
        """Find bridge users who connect different communities.

        Args:
            top_n: Number of bridges to return

        Returns:
            List of (user_id, betweenness_score) tuples
        """
        if not NETWORKX_AVAILABLE or not self.graph:
            logger.warning("NetworkX required for bridge detection")
            return []

        try:
            betweenness = nx.betweenness_centrality(self.graph)
            sorted_users = sorted(betweenness.items(), key=lambda x: x[1], reverse=True)
            return sorted_users[:top_n]
        except Exception as e:
            logger.error(f"Error finding bridges: {e}")
            return []

    def get_shortest_path(self, user_id_1: int, user_id_2: int) -> Optional[List[int]]:
        """Find shortest path between two users.

        Args:
            user_id_1: First user ID
            user_id_2: Second user ID

        Returns:
            List of user IDs in path, or None
        """
        if not NETWORKX_AVAILABLE or not self.graph:
            return None

        try:
            path = nx.shortest_path(self.graph, user_id_1, user_id_2)
            return path
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return None

    def get_network_stats(self) -> Dict:
        """Get overall network statistics.

        Returns:
            Dictionary with network stats
        """
        stats = {}

        conn = self._get_connection()
        cursor = conn.cursor()

        # Node count
        cursor.execute("SELECT COUNT(*) FROM network_nodes")
        stats["total_nodes"] = cursor.fetchone()[0]

        # Edge count
        cursor.execute("SELECT COUNT(*) FROM network_edges")
        stats["total_connections"] = cursor.fetchone()[0]

        # Average connections
        cursor.execute("SELECT AVG(connections) FROM network_nodes")
        stats["avg_connections"] = cursor.fetchone()[0] or 0.0

        # Cluster count
        cursor.execute(
            "SELECT COUNT(DISTINCT cluster_id) FROM network_nodes WHERE cluster_id IS NOT NULL"
        )
        stats["total_clusters"] = cursor.fetchone()[0]

        conn.close()

        # NetworkX stats
        if NETWORKX_AVAILABLE and self.graph:
            stats["network_density"] = nx.density(self.graph)
            if nx.is_connected(self.graph):
                stats["average_path_length"] = nx.average_shortest_path_length(self.graph)
            else:
                stats["average_path_length"] = None

        return stats

    def rebuild_graph_from_db(self):
        """Rebuild in-memory graph from database."""
        if not NETWORKX_AVAILABLE:
            return

        self.graph = nx.Graph()

        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT user_id_1, user_id_2, strength FROM network_edges")

        for row in cursor.fetchall():
            self.graph.add_edge(row[0], row[1], weight=row[2])

        conn.close()
        logger.info(
            f"Rebuilt graph: {self.graph.number_of_nodes()} nodes, {self.graph.number_of_edges()} edges"
        )

    def export_graph_json(self) -> str:
        """Export graph as JSON for visualization.

        Returns:
            JSON string
        """
        if not NETWORKX_AVAILABLE or not self.graph:
            return "{}"

        from networkx.readwrite import json_graph

        data = json_graph.node_link_data(self.graph)
        return json.dumps(data, indent=2)
