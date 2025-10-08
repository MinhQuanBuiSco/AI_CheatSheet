"""Data clustering using embeddings and ML algorithms."""

from dataclasses import dataclass

import numpy as np
import polars as pl
from sentence_transformers import SentenceTransformer
from sklearn.cluster import DBSCAN, AgglomerativeClustering, KMeans  # type: ignore[import-untyped]
from sklearn.preprocessing import StandardScaler  # type: ignore[import-untyped]


@dataclass
class ClusteringConfig:
    """Configuration for clustering operations."""

    algorithm: str = "kmeans"  # kmeans, dbscan, hierarchical
    num_clusters: int = 5
    embedding_model: str = "all-MiniLM-L6-v2"
    normalize: bool = True
    random_state: int = 42
    # DBSCAN parameters
    eps: float = 0.5
    min_samples: int = 5
    # Hierarchical parameters
    linkage: str = "ward"


class DataClusterer:
    """Clusters data using embeddings and various ML algorithms."""

    def __init__(self, config: ClusteringConfig):
        self.config = config
        self._embedding_model: SentenceTransformer | None = None
        self._scaler: StandardScaler | None = None

    def _get_embedding_model(self) -> SentenceTransformer:
        """Lazy load embedding model."""
        if self._embedding_model is None:
            self._embedding_model = SentenceTransformer(self.config.embedding_model)
        return self._embedding_model

    def generate_embeddings(self, texts: list[str]) -> np.ndarray:
        """Generate embeddings for texts.

        Args:
            texts: List of text strings

        Returns:
            NumPy array of embeddings
        """
        model = self._get_embedding_model()
        embeddings = model.encode(texts, show_progress_bar=True)
        return embeddings

    def cluster_embeddings(
        self,
        embeddings: np.ndarray,
        algorithm: str | None = None,
    ) -> np.ndarray:
        """Cluster embeddings using specified algorithm.

        Args:
            embeddings: Input embeddings
            algorithm: Clustering algorithm (uses config if None)

        Returns:
            Cluster labels
        """
        algorithm = algorithm or self.config.algorithm

        # Normalize if configured
        if self.config.normalize:
            if self._scaler is None:
                self._scaler = StandardScaler()
                embeddings_scaled = self._scaler.fit_transform(embeddings)
            else:
                embeddings_scaled = self._scaler.transform(embeddings)
        else:
            embeddings_scaled = embeddings

        # Apply clustering algorithm
        if algorithm == "kmeans":
            clusterer = KMeans(
                n_clusters=self.config.num_clusters,
                random_state=self.config.random_state,
            )
        elif algorithm == "dbscan":
            clusterer = DBSCAN(
                eps=self.config.eps,
                min_samples=self.config.min_samples,
            )
        elif algorithm == "hierarchical":
            clusterer = AgglomerativeClustering(
                n_clusters=self.config.num_clusters,
                linkage=self.config.linkage,
            )
        else:
            raise ValueError(f"Unsupported algorithm: {algorithm}")

        labels = clusterer.fit_predict(embeddings_scaled)
        return labels  # type: ignore[no-any-return]

    def cluster_texts(
        self,
        texts: list[str],
        return_embeddings: bool = False,
    ) -> np.ndarray | tuple[np.ndarray, np.ndarray]:
        """Cluster texts end-to-end.

        Args:
            texts: List of text strings
            return_embeddings: Return embeddings along with labels

        Returns:
            Cluster labels, or (labels, embeddings) if return_embeddings=True
        """
        # Generate embeddings
        embeddings = self.generate_embeddings(texts)

        # Cluster
        labels = self.cluster_embeddings(embeddings)

        if return_embeddings:
            return labels, embeddings
        return labels

    def cluster_dataframe(
        self,
        df: pl.DataFrame,
        text_column: str,
        label_column: str = "cluster",
    ) -> pl.DataFrame:
        """Add cluster labels to DataFrame.

        Args:
            df: Input DataFrame
            text_column: Column containing text to cluster
            label_column: Name for new cluster label column

        Returns:
            DataFrame with cluster labels added
        """
        texts = df[text_column].to_list()
        labels = self.cluster_texts(texts)

        return df.with_columns(pl.Series(label_column, labels))

    def get_cluster_summaries(
        self,
        df: pl.DataFrame,
        text_column: str,
        cluster_column: str = "cluster",
        top_n: int = 5,
    ) -> dict[int, dict]:
        """Get summary statistics for each cluster.

        Args:
            df: DataFrame with cluster labels
            text_column: Column containing text
            cluster_column: Column containing cluster labels
            top_n: Number of top samples to include

        Returns:
            Dictionary mapping cluster ID to summary info
        """
        summaries = {}

        unique_clusters = df[cluster_column].unique().to_list()

        for cluster_id in unique_clusters:
            cluster_df = df.filter(pl.col(cluster_column) == cluster_id)

            summary = {
                "cluster_id": cluster_id,
                "size": len(cluster_df),
                "percentage": len(cluster_df) / len(df) * 100,
                "samples": cluster_df[text_column].head(top_n).to_list(),
            }

            summaries[cluster_id] = summary

        return summaries

    def find_similar(
        self,
        query: str,
        texts: list[str],
        top_k: int = 5,
    ) -> list[tuple[int, float]]:
        """Find similar texts to query.

        Args:
            query: Query text
            texts: List of candidate texts
            top_k: Number of top results

        Returns:
            List of (index, similarity_score) tuples
        """
        model = self._get_embedding_model()

        # Encode query and texts
        query_embedding = model.encode([query])[0]
        text_embeddings = model.encode(texts)

        # Compute cosine similarities
        similarities = np.dot(text_embeddings, query_embedding) / (
            np.linalg.norm(text_embeddings, axis=1) * np.linalg.norm(query_embedding)
        )

        # Get top-k
        top_indices = np.argsort(similarities)[::-1][:top_k]
        results = [(int(idx), float(similarities[idx])) for idx in top_indices]

        return results
