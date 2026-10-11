"""Structure of the OrcaSlicer-ready 3mf (orca3mf.py)."""
import os
import tempfile
import xml.etree.ElementTree as ET
import zipfile

import numpy as np

from _helpers import make_key
from orca3mf import export_orca_3mf, mesh_of

NS = {"m": "http://schemas.microsoft.com/3dmanufacturing/core/2015/02"}


def _parts(k):
    return {"body": k.shape(), "legend": k.legend_plug(), "stem": k.stem_guard()}


def _export():
    keys = [("q", (20.0, 20.0), _parts(make_key(legends=[{"text": "Q"}]))),
            ("blank", (40.0, 20.0), _parts(make_key(legends=[])))]
    path = os.path.join(tempfile.mkdtemp(), "set.orca.3mf")
    export_orca_3mf(keys, path)
    with zipfile.ZipFile(path) as z:
        model = ET.fromstring(z.read("3D/3dmodel.model"))
        config = ET.fromstring(z.read("Metadata/model_settings.config"))
    return model, config


def test_mesh_is_closed():
    # every edge shared by exactly two triangles once duplicates are merged
    _, t = mesh_of(make_key(legends=[{"text": "Q"}]).legend_plug())
    e = np.sort(np.vstack([t[:, [0, 1]], t[:, [1, 2]], t[:, [2, 0]]]), axis=1)
    _, counts = np.unique(e, axis=0, return_counts=True)
    assert (counts == 2).all()


def test_only_parents_are_build_items():
    model, _ = _export()
    objs = {o.get("id"): o for o in model.iterfind("m:resources/m:object", NS)}
    items = [i.get("objectid") for i in model.iterfind("m:build/m:item", NS)]
    assert len(items) == 2
    for oid in items:
        comps = objs[oid].findall("m:components/m:component", NS)
        assert comps, "build item must be a parent with components"
        for c in comps:
            assert objs[c.get("objectid")].find("m:mesh", NS) is not None


def test_part_types_and_filaments():
    model, config = _export()
    by_name = {}
    for obj in config.iter("object"):
        for part in obj.iter("part"):
            md = {m.get("key"): m.get("value") for m in part.iter("metadata")}
            by_name[md["name"]] = (part.get("subtype"), md.get("extruder"))
    assert by_name["q"] == ("normal_part", "1")
    assert by_name["q.legend"] == ("normal_part", "2")
    assert by_name["q.stem"] == ("support_blocker", None)
    # a key without legends has no legend part
    assert "blank.legend" not in by_name and "blank" in by_name


def test_part_ids_match_components():
    model, config = _export()
    objs = {o.get("id"): o for o in model.iterfind("m:resources/m:object", NS)}
    for obj in config.iter("object"):
        comp_ids = [c.get("objectid") for c in
                    objs[obj.get("id")].findall("m:components/m:component", NS)]
        assert [p.get("id") for p in obj.iter("part")] == comp_ids


if __name__ == "__main__":
    test_mesh_is_closed(); print("OK mesh closed after vertex merge")
    test_only_parents_are_build_items(); print("OK only parents are build items")
    test_part_types_and_filaments(); print("OK part types and filaments")
    test_part_ids_match_components(); print("OK part ids match components")
