from pathlib import Path
from gui import _coletar_arquivos


def test_expande_pasta_plana(tmp_path):
    (tmp_path / "a.pdf").touch()
    (tmp_path / "b.pdf").touch()
    pares = _coletar_arquivos([tmp_path])
    nomes = sorted(p[0].name for p in pares)
    assert nomes == ["a.pdf", "b.pdf"]


def test_pasta_saida_para_pasta(tmp_path):
    (tmp_path / "a.pdf").touch()
    pares = _coletar_arquivos([tmp_path])
    assert pares[0][1] == tmp_path / "LIMPOS"


def test_pasta_saida_para_arquivo_individual(tmp_path):
    pdf = tmp_path / "doc.pdf"
    pdf.touch()
    pares = _coletar_arquivos([pdf])
    assert pares[0][1] == tmp_path / "LIMPOS"


def test_filtra_stem_limpo(tmp_path):
    (tmp_path / "a.pdf").touch()
    (tmp_path / "a_limpo.pdf").touch()
    pares = _coletar_arquivos([tmp_path])
    assert len(pares) == 1
    assert pares[0][0].name == "a.pdf"


def test_deduplica_arquivo_repetido(tmp_path):
    pdf = tmp_path / "a.pdf"
    pdf.touch()
    pares = _coletar_arquivos([pdf, pdf])
    assert len(pares) == 1


def test_mix_pasta_e_arquivo(tmp_path):
    sub = tmp_path / "sub"
    sub.mkdir()
    pdf_a = sub / "a.pdf"
    pdf_b = tmp_path / "b.pdf"
    pdf_a.touch()
    pdf_b.touch()
    pares = _coletar_arquivos([sub, pdf_b])
    arquivos = {p[0] for p in pares}
    assert pdf_a in arquivos
    assert pdf_b in arquivos


def test_expande_subpastas(tmp_path):
    sub = tmp_path / "sub"
    sub.mkdir()
    pdf = sub / "nested.pdf"
    pdf.touch()
    pares = _coletar_arquivos([tmp_path])
    assert pares[0][0] == pdf
    assert pares[0][1] == tmp_path / "LIMPOS"
