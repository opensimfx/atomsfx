"""A tiny builder for shader node trees: every helper returns an output socket so expressions compose.

    b = Builder(tree)
    h = b.math("MULTIPLY", d.z, 2.0)
    col = b.mix(fac, a, b)             # data_type inferred from the operands

Constants are written to the socket default; sockets are linked. Nothing here knows about AtmosFX.
"""
from __future__ import annotations

import bpy

Socket = bpy.types.NodeSocket


def _enabled(sockets, name: str):
    for s in sockets:
        if s.name == name and s.enabled:
            return s
    raise KeyError(f"no enabled socket {name!r}")


class Builder:
    def __init__(self, tree: bpy.types.NodeTree, step: float = 220.0):
        self.tree = tree
        self.step = step
        self.x = 0.0
        self.y = 0.0

    # ------------------------------------------------------------------ plumbing
    def set(self, sock: Socket, value) -> None:
        if isinstance(value, Socket):
            self.tree.links.new(value, sock)
        elif value is None:
            return
        else:
            try:
                sock.default_value = value
            except TypeError:
                sock.default_value = tuple(value)

    def node(self, idname: str, label: str | None = None, inputs: dict | None = None, **props):
        n = self.tree.nodes.new(idname)
        for k, v in props.items():
            setattr(n, k, v)
        if label:
            n.label = label
            n.name = label
        n.location = (self.x, self.y)
        self.x += self.step * 0.45
        self.y -= 60.0
        if self.y < -1400:
            self.y = 0.0
            self.x += self.step
        if inputs:
            for key, v in inputs.items():
                s = n.inputs[key] if isinstance(key, int) else _enabled(n.inputs, key)
                self.set(s, v)
        return n

    def col(self) -> None:
        """Start a new layout column."""
        self.x += self.step
        self.y = 0.0

    # --------------------------------------------------------------------- values
    def value(self, v: float, label: str | None = None) -> Socket:
        n = self.node("ShaderNodeValue", label)
        n.outputs[0].default_value = v
        return n.outputs[0]

    def rgb(self, c, label: str | None = None) -> Socket:
        n = self.node("ShaderNodeRGB", label)
        n.outputs[0].default_value = (*c[:3], 1.0)
        return n.outputs[0]

    # ----------------------------------------------------------------------- math
    def math(self, op: str, a, b=None, c=None, clamp: bool = False) -> Socket:
        n = self.node("ShaderNodeMath", operation=op, use_clamp=clamp)
        for i, v in enumerate((a, b, c)):
            if v is not None:
                self.set(n.inputs[i], v)
        return n.outputs[0]

    def vmath(self, op: str, a, b=None, c=None, scale=None, out: str = "Vector") -> Socket:
        n = self.node("ShaderNodeVectorMath", operation=op)
        for i, v in enumerate((a, b, c)):
            if v is not None:
                self.set(n.inputs[i], v)
        if scale is not None:
            self.set(n.inputs["Scale"], scale)
        return n.outputs[out]

    def dot(self, a, b) -> Socket:
        return self.vmath("DOT_PRODUCT", a, b, out="Value")

    def length(self, a) -> Socket:
        return self.vmath("LENGTH", a, out="Value")

    def normalize(self, a) -> Socket:
        return self.vmath("NORMALIZE", a)

    def sep(self, v):
        n = self.node("ShaderNodeSeparateXYZ")
        self.set(n.inputs[0], v)
        return n.outputs[0], n.outputs[1], n.outputs[2]

    def comb(self, x=0.0, y=0.0, z=0.0) -> Socket:
        n = self.node("ShaderNodeCombineXYZ")
        for k, v in zip(("X", "Y", "Z"), (x, y, z)):
            self.set(n.inputs[k], v)
        return n.outputs[0]

    def map_range(self, v, fmin=0.0, fmax=1.0, tmin=0.0, tmax=1.0, clamp: bool = True, interp: str = "LINEAR") -> Socket:
        n = self.node("ShaderNodeMapRange", data_type="FLOAT", interpolation_type=interp, clamp=clamp)
        for k, x in (("Value", v), ("From Min", fmin), ("From Max", fmax), ("To Min", tmin), ("To Max", tmax)):
            self.set(_enabled(n.inputs, k), x)
        return _enabled(n.outputs, "Result")

    def smoothstep(self, v, e0, e1) -> Socket:
        return self.map_range(v, e0, e1, 0.0, 1.0, True, "SMOOTHSTEP")

    def mix(self, fac, a, b, kind: str = "FLOAT") -> Socket:
        n = self.node("ShaderNodeMix", data_type=kind)
        self.set(_enabled(n.inputs, "Factor"), fac)
        self.set(_enabled(n.inputs, "A"), a if kind != "RGBA" or isinstance(a, Socket) or len(a) == 4 else (*a, 1.0))
        self.set(_enabled(n.inputs, "B"), b if kind != "RGBA" or isinstance(b, Socket) or len(b) == 4 else (*b, 1.0))
        return _enabled(n.outputs, "Result")

    def mix_rgb(self, fac, a, b) -> Socket:
        return self.mix(fac, a, b, "RGBA")

    def mix_vec(self, fac, a, b) -> Socket:
        n = self.node("ShaderNodeMix", data_type="VECTOR")
        self.set(_enabled(n.inputs, "Factor"), fac)
        self.set(_enabled(n.inputs, "A"), a)
        self.set(_enabled(n.inputs, "B"), b)
        return _enabled(n.outputs, "Result")

    def scale_rgb(self, color, k) -> Socket:
        """Multiply a colour by a scalar (Mix node in MULTIPLY blend with a grey factor would clip)."""
        n = self.node("ShaderNodeVectorMath", operation="SCALE")
        self.set(n.inputs[0], color)
        self.set(n.inputs["Scale"], k)
        return n.outputs[0]

    def mul_rgb(self, a, b) -> Socket:
        n = self.node("ShaderNodeVectorMath", operation="MULTIPLY")
        self.set(n.inputs[0], a)
        self.set(n.inputs[1], b)
        return n.outputs[0]

    def add_rgb(self, a, b) -> Socket:
        n = self.node("ShaderNodeVectorMath", operation="ADD")
        self.set(n.inputs[0], a)
        self.set(n.inputs[1], b)
        return n.outputs[0]

    def luminance(self, rgb) -> Socket:
        return self.dot(rgb, (0.2126, 0.7152, 0.0722))

    # -------------------------------------------------------------------- textures
    def noise(self, vec, scale=1.0, detail=2.0, roughness=0.5, w=None, dims: str = "3D", lacunarity: float = 2.0,
              distortion: float = 0.0) -> Socket:
        n = self.node("ShaderNodeTexNoise", noise_dimensions=dims, noise_type="FBM", normalize=True)
        self.set(n.inputs["Vector"], vec)
        self.set(n.inputs["Scale"], scale)
        self.set(n.inputs["Detail"], detail)
        self.set(n.inputs["Roughness"], roughness)
        self.set(n.inputs["Lacunarity"], lacunarity)
        self.set(n.inputs["Distortion"], distortion)
        if w is not None and dims == "4D":
            self.set(n.inputs["W"], w)
        return n.outputs["Fac"]

    def mapping(self, vec, loc=(0, 0, 0), rot=(0, 0, 0), scale=(1, 1, 1)) -> Socket:
        n = self.node("ShaderNodeMapping", vector_type="POINT")
        self.set(n.inputs["Vector"], vec)
        self.set(n.inputs["Location"], loc)
        self.set(n.inputs["Rotation"], rot)
        self.set(n.inputs["Scale"], scale)
        return n.outputs[0]

    # ------------------------------------------------------------ group interface
    @staticmethod
    def add_input(tree, name: str, socket_type: str, default=None, lo=None, hi=None, tooltip: str = ""):
        s = tree.interface.new_socket(name=name, in_out="INPUT", socket_type=socket_type)
        if default is not None:
            s.default_value = default
        if lo is not None and hasattr(s, "min_value"):
            s.min_value = lo
        if hi is not None and hasattr(s, "max_value"):
            s.max_value = hi
        if tooltip:
            s.description = tooltip
        return s

    @staticmethod
    def add_output(tree, name: str, socket_type: str):
        return tree.interface.new_socket(name=name, in_out="OUTPUT", socket_type=socket_type)
