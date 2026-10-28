from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def test_security_md_cobre_o_risco_registrado_no_design():
    security_md = (REPO_ROOT / "deploy" / "SECURITY.md").read_text(encoding="utf-8")
    design_md = (REPO_ROOT / "openspec" / "changes" / "webtop-portal" / "design.md").read_text(
        encoding="utf-8"
    )

    for termo in ["socket-proxy", "root no host", "componente de confiança"]:
        assert termo in security_md, f"termo ausente em SECURITY.md: {termo}"
        assert termo in design_md, f"termo ausente em design.md: {termo}"
