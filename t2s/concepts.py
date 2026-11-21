"""4층 개념 요약(Ossie ontology/ontology.md, mapping): 질문의 업무 말을 정의 필드로 옮길 때 LLM 이 본다.

정의 파일 옆의 *.mapping.yaml 중 semantic_model_ref.iri 가 그 정의 파일을 가리키는 것을 쓰고, 그 매핑의 ontology_ref.iri 로 온톨로지를 읽는다.
매핑은 개념(EntityType)의 관계를 데이터셋 필드에 잇는다. 지표는 잇지 않는다(규격에 칸이 없다).
"""
from __future__ import annotations

from pathlib import Path

from .ossie import read_yaml


def find(model_path: str) -> tuple[dict, dict] | None:
    """(온톨로지, 매핑). 정의 파일을 가리키는 매핑이 없으면 None."""
    model = Path(model_path).resolve()
    for path in sorted(model.parent.glob("*.mapping.yaml")):
        mapping = read_yaml(path)
        iri = ((mapping or {}).get("semantic_model_ref") or {}).get("iri")
        if iri and (path.parent / iri).resolve() == model:
            onto = (mapping.get("ontology_ref") or {}).get("iri")
            onto_path = path.parent / onto if onto else None
            return (read_yaml(onto_path) if onto_path and onto_path.is_file() else {}), mapping
    return None


def _referents(items: list, prefix: str = "") -> list[tuple[str, str]]:
    """referent_mappings → [(관계 경로, 식)]. 겹친 referent 는 order.id 처럼 잇는다."""
    out = []
    for r in items or []:
        path = f"{prefix}{r['relationship']}"
        if r.get("expression"):
            out.append((path, r["expression"]))
        out += _referents(r.get("referent_mappings"), path + ".")
    return out


def summary(onto: dict, mapping: dict) -> str:
    """개념마다 설명과 '관계 = dataset.field' 목록 한 줄."""
    concepts = {c["concept"]: c for c in (onto or {}).get("ontology") or []}
    lines = ["개념 (질문의 업무 말을 이 필드로 옮긴다. 관계 = dataset.field)"]
    for cm in mapping.get("concept_mappings") or []:
        name = cm["concept"]
        pairs = [p for om in cm.get("object_mappings") or [] for p in _referents(om.get("referent_mappings"))]
        for lm in cm.get("link_mappings") or []:
            for child in lm.get("children") or []:
                om = child.get("object_mapping") or {}
                expr = om.get("expression") or ", ".join(e for _, e in _referents(om.get("referent_mappings")))
                pairs.append((child["relationship"], f"{expr}{f' ({om['concept']})' if om.get('concept') else ''}"))
        seen = list(dict.fromkeys(f"{rel} = {expr}" for rel, expr in pairs))
        lines.append(f"- {name}: " + " / ".join(filter(None, [concepts.get(name, {}).get("description", ""), "; ".join(seen)])))
    return "\n".join(lines)
