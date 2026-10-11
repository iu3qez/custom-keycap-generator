"""OrcaSlicer-ready 3mf export: one object per key, parts pre-typed.

Each key is one 3MF parent <object> whose <components> reference three child
objects (body, legend, stem), each with its own mesh. Only the parent is a
<build> item. Metadata/model_settings.config lists each child as a <part> and
sets its type, name and filament, so Orca opens the file ready to slice:

    body    normal_part      extruder 1
    legend  normal_part      extruder 2   (all glyphs in one part)
    stem    support_blocker               (no supports inside the cross)

Format as read by OrcaSlicer src/libslic3r/Format/bbs_3mf.cpp:
- parts are built by _generate_volumes_new from the parent's components;
  <part id=...> is matched to the child object id. (The triangle-range
  firstid/lastid path, _generate_volumes, is commented out in Orca.)
- <metadata key="name"> names the part; any other key (e.g. "extruder") goes
  to the part's config via set_deserialize.
- subtype strings come from ModelVolume::type_from_string (Model.cpp).
"""
import zipfile
from xml.sax.saxutils import quoteattr

import numpy as np

# (role, subtype, extruder or None)
PART_ROLES = {
    "body": ("normal_part", 1),
    "legend": ("normal_part", 2),
    "stem": ("support_blocker", None),
}

_CONTENT_TYPES = """<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
 <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
 <Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/>
 <Default Extension="config" ContentType="text/xml"/>
</Types>
"""

_RELS = """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
 <Relationship Target="/3D/3dmodel.model" Id="rel0" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/>
</Relationships>
"""


# Linear tessellation tolerance in mm: 10 um, far below a 0.1 mm layer. (build123d
# Mesher defaults to 0.001, which makes a whole-set file several hundred MB.)
TOLERANCE = 0.01


def mesh_of(shape, tolerance: float = TOLERANCE, angular_tolerance: float = 0.1):
    """Tessellate a build123d shape into (vertices Nx3, triangles Mx3) with
    duplicate vertices merged, so the mesh is closed (tessellate() repeats
    vertices on every shared face edge)."""
    verts, tris = shape.tessellate(tolerance, angular_tolerance)
    v = np.array([[p.X, p.Y, p.Z] for p in verts], dtype=float)
    t = np.array(tris, dtype=np.int64).reshape(-1, 3)
    key = np.round(v / 1e-6).astype(np.int64)
    _, first, inverse = np.unique(key, axis=0, return_index=True, return_inverse=True)
    v = v[first]
    t = inverse.reshape(-1)[t]
    t = t[(t[:, 0] != t[:, 1]) & (t[:, 1] != t[:, 2]) & (t[:, 0] != t[:, 2])]
    return v, t


def export_orca_3mf(keys, path, tolerance: float = TOLERANCE):
    """Write keys to one OrcaSlicer-ready 3mf.

    keys: iterable of (name, (x, y), parts) where parts maps a role in
    PART_ROLES ("body", "legend", "stem") to a build123d shape or None, and
    (x, y) is the key's position on the plate in mm.
    """
    resources, build = [], []
    config = ['<?xml version="1.0" encoding="UTF-8"?>\n<config>\n']
    next_id = 1

    for name, (x, y), parts in keys:
        children = []                      # (sub-object id, role)
        for role, shape in parts.items():
            if shape is None:
                continue
            v, t = mesh_of(shape, tolerance)
            label = name if role == "body" else f"{name}.{role}"
            resources.append(f'  <object id="{next_id}" name={quoteattr(label)} type="model">\n'
                             '   <mesh>\n    <vertices>\n')
            resources.extend(f'     <vertex x="{a:.6f}" y="{b:.6f}" z="{c:.6f}"/>\n' for a, b, c in v)
            resources.append('    </vertices>\n    <triangles>\n')
            resources.extend(f'     <triangle v1="{a}" v2="{b}" v3="{c}"/>\n' for a, b, c in t)
            resources.append('    </triangles>\n   </mesh>\n  </object>\n')
            children.append((next_id, role, label))
            next_id += 1

        parent = next_id
        next_id += 1
        resources.append(f'  <object id="{parent}" name={quoteattr(name)} type="model">\n'
                         '   <components>\n')
        resources.extend(f'    <component objectid="{cid}"/>\n' for cid, _, _ in children)
        resources.append('   </components>\n  </object>\n')
        build.append(f'  <item objectid="{parent}" '
                     f'transform="1 0 0 0 1 0 0 0 1 {x:.6f} {y:.6f} 0"/>\n')

        config.append(f' <object id="{parent}">\n'
                      f'  <metadata key="name" value={quoteattr(name)}/>\n'
                      '  <metadata key="extruder" value="1"/>\n')
        for cid, role, label in children:
            subtype, extruder = PART_ROLES[role]
            config.append(f'  <part id="{cid}" subtype="{subtype}">\n'
                          f'   <metadata key="name" value={quoteattr(label)}/>\n')
            if extruder is not None:
                config.append(f'   <metadata key="extruder" value="{extruder}"/>\n')
            config.append('  </part>\n')
        config.append(' </object>\n')
    config.append('</config>\n')

    model = ('<?xml version="1.0" encoding="UTF-8"?>\n'
             '<model unit="millimeter" xml:lang="en-US" '
             'xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02">\n'
             ' <resources>\n' + "".join(resources) + ' </resources>\n'
             ' <build>\n' + "".join(build) + ' </build>\n</model>\n')

    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", _CONTENT_TYPES)
        z.writestr("_rels/.rels", _RELS)
        z.writestr("3D/3dmodel.model", model)
        z.writestr("Metadata/model_settings.config", "".join(config))
