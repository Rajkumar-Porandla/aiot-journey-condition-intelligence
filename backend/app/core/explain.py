"""Local explanations for the trained Random Forest models.

Method: *tree path contributions* (Saabas, also known as "treeinterpreter").
For every tree, the prediction equals the root-node value plus the sum of the
value changes produced by each split along the decision path. Attributing each
change to the split's feature and averaging over all trees gives an exact,
deterministic decomposition::

    prediction = base_value + sum(feature_contributions)

This needs no extra dependency (SHAP's TreeExplainer would add numba/llvmlite)
and is computed from the actual fitted trees, so explanations are never random.
Global importance is provided separately by grouped permutation importance
(computed at training time on the held-out test journeys).
"""
import numpy as np


def _node_values(tree, is_classifier):
    values = tree.tree_.value[:, 0, :]  # (n_nodes, n_outputs/classes)
    if is_classifier:
        sums = values.sum(axis=1, keepdims=True)
        sums[sums == 0] = 1.0
        values = values / sums
    return values


def tree_contributions(forest, x_row):
    """Return (base_value, contributions) for a single sample.

    Regressor: base -> float, contributions -> (n_features,)
    Classifier: base -> (n_classes,), contributions -> (n_features, n_classes)
    """
    x = np.asarray(x_row, dtype=np.float64).reshape(1, -1)
    is_classifier = hasattr(forest, "classes_")
    n_features = x.shape[1]
    n_out = len(forest.classes_) if is_classifier else 1
    base_total = np.zeros(n_out)
    contrib_total = np.zeros((n_features, n_out))

    for est in forest.estimators_:
        values = _node_values(est, is_classifier)
        feature = est.tree_.feature
        # Node ids along the path; sklearn always numbers children after their parent,
        # so sorting yields root -> leaf order.
        path = np.sort(est.decision_path(x).indices)
        base_total += values[path[0]]
        for parent, child in zip(path[:-1], path[1:]):
            contrib_total[feature[parent]] += values[child] - values[parent]

    n_trees = len(forest.estimators_)
    base = base_total / n_trees
    contrib = contrib_total / n_trees
    if not is_classifier:
        return float(base[0]), contrib[:, 0]
    return base, contrib
