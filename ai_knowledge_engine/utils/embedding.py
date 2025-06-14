import numpy as np
import pickle

def _load_trained_model(file: str):
    """load pre trained model"""
    import os
    model_path = os.path.dirname(os.path.abspath(__file__)) + '/../../trained_models'
    os.makedirs(model_path, exist_ok=True)

    path = os.path.join(model_path, file)
    with open(path, 'rb') as f:
        model = pickle.load(f)
    return model


def _tranform_embedding(embeddings):
    scaler = _load_trained_model("scaler_embedding.pkl")
    pca = _load_trained_model("pca_embedding.pkl")
    umap_reducer = _load_trained_model("umap_reducer_embedding.pkl")

    embeddings = np.array(embeddings)
    # must be 2darray
    if embeddings.ndim == 1:
        embeddings = embeddings.reshape(1, -1)

    embedding_scaled = scaler.transform(embeddings)
    embedding_pca = pca.transform(embedding_scaled)
    embedding_reduced = umap_reducer.transform(embedding_pca)

    return embedding_reduced.tolist()