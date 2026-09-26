import pytest
from brain_options.specialist.peer_genome import (
    extract_genome,
    PeerGenomeGraph,
    AlphaGenome,
)
from tests.fixtures.known_expressions import (
    KNOWN_LEVEYPMX_EXPR,
    KNOWN_KPND6OVL_EXPR,
    KNOWN_E5PNPQLM_EXPR,
    KNOWN_YPB81N2V_EXPR,
    KNOWN_GJBAP76E_EXPR,
    KNOWN_ALPHAS,
)


def test_levEYpmx_genome_is_blended_call_put_iv_term():
    genome = extract_genome("levEYpmx", KNOWN_LEVEYPMX_EXPR, decay=15)
    assert set(genome.tenors) >= {90, 180}
    assert "put" in genome.moneyness
    assert "call" in genome.moneyness
    assert "pcr" in genome.factors
    assert "iv_term_structure" in genome.factors
    assert genome.decay == 15


def test_kpnd6ovl_genome_is_30d_call_pcr():
    genome = extract_genome("KPNd6Ovl", KNOWN_KPND6OVL_EXPR, decay=8)
    assert 30 in genome.tenors
    assert genome.moneyness == ["call"]
    assert "pcr" in genome.factors
    assert genome.decay == 8


def test_ypb81n2v_genome_is_180d_call_pcr():
    genome = extract_genome("YPb81N2v", KNOWN_YPB81N2V_EXPR, decay=16)
    assert 180 in genome.tenors
    assert genome.moneyness == ["call"]
    assert "pcr" in genome.factors
    assert genome.decay == 16


def test_e5pnpqlm_genome_is_90d_call_put_iv():
    genome = extract_genome("E5pNpQlm", KNOWN_E5PNPQLM_EXPR, decay=7)
    assert 90 in genome.tenors
    assert genome.moneyness == ["call"]
    assert "call_put_iv_ratio" in genome.factors
    assert genome.decay == 7


def test_gjbap76e_genome_is_30d_call_skew():
    genome = extract_genome("gJbAP76e", KNOWN_GJBAP76E_EXPR, decay=18)
    assert 30 in genome.tenors
    assert genome.moneyness == ["call"]
    assert "skew" in genome.factors
    assert genome.decay == 18


def test_peer_genome_graph_collision_detection():
    genomes = [
        extract_genome("KPNd6Ovl", KNOWN_KPND6OVL_EXPR, decay=8),
        extract_genome("levEYpmx", KNOWN_LEVEYPMX_EXPR, decay=15),
    ]
    graph = PeerGenomeGraph(genomes)

    # Exact collision with KPNd6Ovl on 30d call pcr
    collision = graph.find_collision_risk(tenor=30, moneyness="call", factor="pcr", decay=8)
    assert collision is not None
    assert collision.alpha_id == "KPNd6Ovl"

    # Collision with levEYpmx on 90d put iv_term_structure
    collision_lev = graph.find_collision_risk(tenor=90, moneyness="put", factor="iv_term_structure", decay=15)
    assert collision_lev is not None
    assert collision_lev.alpha_id == "levEYpmx"

    # Free cell (60d put iv_term_structure) -> No collision
    free_cell = graph.find_collision_risk(tenor=60, moneyness="put", factor="iv_term_structure", decay=12)
    assert free_cell is None


def test_peer_genome_graph_decay_gap():
    genome = extract_genome("KPNd6Ovl", KNOWN_KPND6OVL_EXPR, decay=8)
    graph = PeerGenomeGraph([genome])
    assert graph.decay_too_close(10, genome, min_gap=7) is True   # abs(10-8) = 2 < 7
    assert graph.decay_too_close(16, genome, min_gap=7) is False  # abs(16-8) = 8 >= 7
