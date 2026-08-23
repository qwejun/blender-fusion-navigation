# SPDX-License-Identifier: GPL-3.0-or-later

bl_info = {
    "name": "Fusion 按键与导航",
    "author": "qwejun",
    "version": (0, 2, 2),
    "blender": (5, 2, 0),
    "location": "编辑 > 偏好设置 > 插件",
    "description": "复刻 Fusion 360 风格的按键、鼠标导航和视图立方体",
    "category": "3D View",
}

import bpy
import blf
import math
from bpy.props import BoolProperty
from bpy.types import Gizmo, GizmoGroup, Operator
from mathutils import Matrix, Vector


_KEYMAP_ITEMS = {
    "navigation": [],
    "shortcuts": [],
}
_NATIVE_NAV_GIZMO_STATE = {}


def _set_group_active(group, active):
    for _keymap, keymap_item in _KEYMAP_ITEMS[group]:
        keymap_item.active = active


def _update_navigation(self, _context):
    _set_group_active("navigation", self.enable_navigation)


def _update_shortcuts(self, _context):
    _set_group_active("shortcuts", self.enable_shortcuts)


class FUSIONKEYS_AddonPreferences(bpy.types.AddonPreferences):
    bl_idname = __package__

    enable_navigation: BoolProperty(
        name="Fusion 鼠标导航",
        description="使用鼠标中键平移，Shift 加鼠标中键旋转视图",
        default=True,
        update=_update_navigation,
    )
    enable_shortcuts: BoolProperty(
        name="Fusion 快捷键",
        description="启用在 Blender 中具有明确对应功能的 Fusion 常用快捷键",
        default=True,
        update=_update_shortcuts,
    )
    enable_view_cube: BoolProperty(
        name="Fusion 视图立方体",
        description="在 3D 视图右上角显示可点击的 Fusion 风格视图立方体",
        default=True,
        update=lambda self, _context: _update_view_cube(self),
    )

    def draw(self, _context):
        layout = self.layout

        layout.prop(self, "enable_navigation")
        navigation = layout.column(align=True)
        navigation.enabled = self.enable_navigation
        navigation.label(text="拖动鼠标中键：平移视图")
        navigation.label(text="Shift + 鼠标中键：旋转视图")
        navigation.label(text="滚动鼠标滚轮：缩放视图（保持 Blender 默认）")

        layout.separator()
        layout.prop(self, "enable_shortcuts")
        shortcuts = layout.column(align=True)
        shortcuts.enabled = self.enable_shortcuts
        shortcuts.label(text="M：移动")
        shortcuts.label(text="F：圆角 / 倒角（编辑模式）")
        shortcuts.label(text="S：搜索命令")
        shortcuts.label(text="I：测量工具")
        shortcuts.label(text="Q：按压拖动 / 挤出区域（编辑模式）")
        shortcuts.label(text="Ctrl + Y：重做")

        layout.separator()
        note = layout.box()
        note.label(text="以下按键与 Fusion 基本一致，因此保持 Blender 默认设置：")
        note.label(text="E：挤出，R：旋转，Delete：删除，Ctrl + Z：撤销")
        layout.separator()
        layout.prop(self, "enable_view_cube")
        layout.label(text="点击立方体的面：正视 / 侧视 / 顶视")
        layout.label(text="点击角：等轴测视图；Home：默认等轴测")


class FUSIONKEYS_OT_view_cube(Operator):
    bl_idname = "view3d.fusion_view_cube"
    bl_label = "Fusion 视图立方体"
    bl_options = {'INTERNAL'}

    direction: bpy.props.EnumProperty(
        items=(
            ('FRONT', "前", "前视图"),
            ('BACK', "后", "后视图"),
            ('LEFT', "左", "左视图"),
            ('RIGHT', "右", "右视图"),
            ('TOP', "顶", "顶视图"),
            ('BOTTOM', "底", "底视图"),
            ('ISO', "等轴测", "默认等轴测视图"),
        ),
        default='ISO',
    )

    def execute(self, context):
        if context.area and context.area.type == 'VIEW_3D':
            if self.direction == 'ISO':
                bpy.ops.view3d.view_axis(type='FRONT')
                bpy.ops.view3d.view_orbit(angle=math.radians(45.0), type='ORBITLEFT')
                bpy.ops.view3d.view_orbit(angle=math.radians(35.264), type='ORBITUP')
            else:
                bpy.ops.view3d.view_axis(type=self.direction)
            return {'FINISHED'}
        return {'CANCELLED'}


_CUBE_FACE_VERTS = (
    (-1.0, -1.0), (1.0, -1.0), (1.0, 1.0),
    (-1.0, -1.0), (1.0, 1.0), (-1.0, 1.0),
)


class FUSIONKEYS_GIZMO_view_cube_face(Gizmo):
    bl_idname = "VIEW3D_GT_fusion_view_cube_face"

    __slots__ = ("custom_shape", "label", "world_vertices", "normal")

    def setup(self):
        if not hasattr(self, "custom_shape"):
            self.custom_shape = self.new_custom_shape('TRIS', _CUBE_FACE_VERTS)

    def draw(self, context):
        self.draw_custom_shape(self.custom_shape)
        if self.hide or not self.label:
            return
        font_id = 0
        font_size = max(10, round(11 * context.preferences.system.ui_scale))
        blf.size(font_id, font_size)
        blf.color(font_id, 0.12, 0.12, 0.12, 1.0)
        width, height = blf.dimensions(font_id, self.label)
        center = self.matrix_world.translation
        blf.position(font_id, center.x - width / 2, center.y - height / 2, 0)
        blf.draw(font_id, self.label)

    def test_select(self, _context, location):
        try:
            local = self.matrix_world.inverted() @ Vector((location[0], location[1], 0.0))
        except ValueError:
            return -1
        return 0 if abs(local.x) <= 1.0 and abs(local.y) <= 1.0 else -1


class FUSIONKEYS_GIZMO_axis_label(Gizmo):
    bl_idname = "VIEW3D_GT_fusion_axis_label"

    __slots__ = ("label",)

    def draw(self, context):
        font_id = 0
        font_size = max(11, round(13 * context.preferences.system.ui_scale))
        blf.size(font_id, font_size)
        blf.color(font_id, self.color[0], self.color[1], self.color[2], 1.0)
        width, height = blf.dimensions(font_id, self.label)
        center = self.matrix_world.translation
        blf.position(font_id, center.x - width / 2, center.y - height / 2, 0)
        blf.draw(font_id, self.label)

    def test_select(self, _context, _location):
        return -1


class FUSIONKEYS_GIZMOGROUP_view_cube(GizmoGroup):
    bl_idname = "VIEW3D_GGT_fusion_view_cube"
    bl_label = "Fusion 视图立方体"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'WINDOW'
    bl_options = {'PERSISTENT', 'SCALE'}

    @classmethod
    def poll(cls, context):
        addon = bpy.context.preferences.addons.get(__package__)
        return bool(addon and addon.preferences.enable_view_cube)

    def setup(self, _context):
        self.faces = []
        self.corners = []
        face_specs = (
            ('RIGHT', "右", (1, 0, 0), ((1, -1, -1), (1, 1, -1), (1, 1, 1), (1, -1, 1))),
            ('LEFT', "左", (-1, 0, 0), ((-1, 1, -1), (-1, -1, -1), (-1, -1, 1), (-1, 1, 1))),
            ('BACK', "后", (0, 1, 0), ((1, 1, -1), (-1, 1, -1), (-1, 1, 1), (1, 1, 1))),
            ('FRONT', "前", (0, -1, 0), ((-1, -1, -1), (1, -1, -1), (1, -1, 1), (-1, -1, 1))),
            ('TOP', "上", (0, 0, 1), ((-1, -1, 1), (1, -1, 1), (1, 1, 1), (-1, 1, 1))),
            ('BOTTOM', "下", (0, 0, -1), ((-1, 1, -1), (1, 1, -1), (1, -1, -1), (-1, -1, -1))),
        )
        for direction, label, normal, vertices in face_specs:
            gz = self.gizmos.new(FUSIONKEYS_GIZMO_view_cube_face.bl_idname)
            gz.target_set_operator("view3d.fusion_view_cube").direction = direction
            gz.label = label
            gz.normal = Vector(normal)
            gz.world_vertices = tuple(Vector(vertex) for vertex in vertices)
            gz.color = (0.72, 0.74, 0.78)
            gz.alpha = 0.94
            gz.color_highlight = (0.20, 0.62, 1.0)
            gz.alpha_highlight = 1.0
            gz.scale_basis = 1.0
            gz.use_tooltip = True
            self.faces.append(gz)

        for vertex in (
            (-1, -1, -1), (-1, -1, 1), (-1, 1, -1), (-1, 1, 1),
            (1, -1, -1), (1, -1, 1), (1, 1, -1), (1, 1, 1),
        ):
            gz = self.gizmos.new(FUSIONKEYS_GIZMO_view_cube_face.bl_idname)
            gz.target_set_operator("view3d.fusion_view_cube").direction = 'ISO'
            gz.label = ""
            gz.world_vertices = (Vector(vertex),)
            gz.normal = Vector((0, 0, 0))
            gz.color = (0.20, 0.62, 1.0)
            gz.alpha = 0.01
            gz.color_highlight = (0.20, 0.62, 1.0)
            gz.alpha_highlight = 1.0
            gz.scale_basis = 5.5
            gz.use_tooltip = True
            self.corners.append(gz)

        home = self.gizmos.new("GIZMO_GT_button_2d")
        home.target_set_operator("view3d.fusion_view_cube").direction = 'ISO'
        home.icon = 'HOME'
        home.draw_options = {'BACKDROP', 'OUTLINE'}
        home.color = (0.55, 0.57, 0.62)
        home.alpha = 0.75
        home.color_highlight = (0.20, 0.62, 1.0)
        home.alpha_highlight = 1.0
        home.scale_basis = 11.0
        home.use_tooltip = True
        self.home = home

        self.axis_labels = []
        for label, axis, color in (
            ('X', Vector((1, 0, 0)), (0.95, 0.18, 0.22)),
            ('Y', Vector((0, 1, 0)), (0.25, 0.88, 0.32)),
            ('Z', Vector((0, 0, 1)), (0.18, 0.48, 1.0)),
        ):
            gz = self.gizmos.new(FUSIONKEYS_GIZMO_axis_label.bl_idname)
            gz.label = label
            gz.color = color
            gz.hide_select = True
            self.axis_labels.append((gz, axis))

    def draw_prepare(self, context):
        region = context.region
        region_3d = context.region_data
        if region_3d is None:
            return

        area_key = (context.window.as_pointer(), context.area.as_pointer())
        if area_key not in _NATIVE_NAV_GIZMO_STATE:
            _NATIVE_NAV_GIZMO_STATE[area_key] = context.space_data.show_gizmo_navigate
        context.space_data.show_gizmo_navigate = False

        ui_scale = context.preferences.system.ui_scale
        # Leave room for the viewport header and its Options popover. Keeping
        # the whole widget inset also prevents axis labels clipping at the edge.
        center = Vector((
            region.width - 104.0 * ui_scale,
            region.height - 118.0 * ui_scale,
        ))
        rotation = region_3d.view_matrix.to_3x3()
        cube_scale = 25.0 * ui_scale

        visible_normals = []
        for gz in self.faces:
            view_normal = rotation @ gz.normal
            visible = view_normal.z > 0.015
            gz.hide = not visible
            if not visible:
                continue
            visible_normals.append(gz.normal)
            projected = []
            for vertex in gz.world_vertices:
                view_vertex = rotation @ vertex
                projected.append(Vector((view_vertex.x, view_vertex.y)) * cube_scale)

            p0, p1, p2, p3 = projected
            axis_x = (p1 - p0) * 0.5
            axis_y = (p3 - p0) * 0.5
            face_center = (p0 + p2) * 0.5 + center
            matrix = Matrix.Identity(4)
            matrix[0][0], matrix[1][0] = axis_x.x, axis_x.y
            matrix[0][1], matrix[1][1] = axis_y.x, axis_y.y
            matrix[0][3], matrix[1][3] = face_center.x, face_center.y
            gz.matrix_basis = matrix

            shade = 0.54 + 0.30 * view_normal.z
            gz.color = (shade, shade + 0.015, min(1.0, shade + 0.035))

        for gz in self.corners:
            vertex = gz.world_vertices[0]
            # Hide only the far corner; the other seven belong to a visible face.
            gz.hide = not any(vertex.dot(normal) > 0 for normal in visible_normals)
            if gz.hide:
                continue
            view_vertex = rotation @ vertex
            projected = Vector((view_vertex.x, view_vertex.y)) * cube_scale
            matrix = Matrix.Identity(4)
            matrix[0][3] = center.x + projected.x
            matrix[1][3] = center.y + projected.y
            gz.matrix_basis = matrix

        self.home.matrix_basis[0][3] = center.x - 49.0 * ui_scale
        self.home.matrix_basis[1][3] = center.y + 18.0 * ui_scale

        for gz, axis in self.axis_labels:
            view_axis = rotation @ axis
            projected = Vector((view_axis.x, view_axis.y))
            if projected.length < 0.18:
                gz.hide = True
                continue
            gz.hide = False
            projected.normalize()
            position = center + projected * cube_scale * 1.72
            matrix = Matrix.Identity(4)
            matrix[0][3], matrix[1][3] = position.x, position.y
            gz.matrix_basis = matrix


def _update_view_cube(_prefs):
    if _prefs.enable_view_cube:
        _hide_native_navigation_gizmo()
    else:
        _restore_native_navigation_gizmo()


def _hide_native_navigation_gizmo():
    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            if area.type != 'VIEW_3D':
                continue
            space = area.spaces.active
            area_key = (window.as_pointer(), area.as_pointer())
            if area_key not in _NATIVE_NAV_GIZMO_STATE:
                _NATIVE_NAV_GIZMO_STATE[area_key] = space.show_gizmo_navigate
            space.show_gizmo_navigate = False
            area.tag_redraw()


def _restore_native_navigation_gizmo():
    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            if area.type != 'VIEW_3D':
                continue
            area_key = (window.as_pointer(), area.as_pointer())
            previous = _NATIVE_NAV_GIZMO_STATE.get(area_key)
            if previous is not None:
                area.spaces.active.show_gizmo_navigate = previous
            area.tag_redraw()
    _NATIVE_NAV_GIZMO_STATE.clear()


def _add_keymap_item(
    group,
    keymap_name,
    operator,
    key,
    value="PRESS",
    *,
    space_type="EMPTY",
    shift=False,
    ctrl=False,
    alt=False,
    properties=None,
):
    keyconfig = bpy.context.window_manager.keyconfigs.addon
    if keyconfig is None:
        return

    keymap = keyconfig.keymaps.get(keymap_name)
    if keymap is None:
        keymap = keyconfig.keymaps.new(
            name=keymap_name,
            space_type=space_type,
            region_type="WINDOW",
        )

    keymap_item = keymap.keymap_items.new(
        operator,
        key,
        value,
        shift=shift,
        ctrl=ctrl,
        alt=alt,
    )
    if properties:
        for name, property_value in properties.items():
            setattr(keymap_item.properties, name, property_value)

    _KEYMAP_ITEMS[group].append((keymap, keymap_item))


def _register_keymaps():
    # Fusion swaps Blender's default middle-mouse actions.
    _add_keymap_item(
        "navigation",
        "3D View",
        "view3d.move",
        "MIDDLEMOUSE",
        space_type="VIEW_3D",
    )
    _add_keymap_item(
        "navigation",
        "3D View",
        "view3d.rotate",
        "MIDDLEMOUSE",
        space_type="VIEW_3D",
        shift=True,
    )

    # Only map Fusion commands that have a close, predictable Blender match.
    _add_keymap_item(
        "shortcuts",
        "3D View",
        "wm.search_menu",
        "S",
        space_type="VIEW_3D",
    )
    _add_keymap_item(
        "shortcuts",
        "3D View",
        "wm.tool_set_by_id",
        "I",
        space_type="VIEW_3D",
        properties={"name": "builtin.measure"},
    )
    _add_keymap_item("shortcuts", "Object Mode", "transform.translate", "M")
    _add_keymap_item("shortcuts", "Mesh", "transform.translate", "M")
    _add_keymap_item("shortcuts", "Mesh", "mesh.bevel", "F")
    _add_keymap_item("shortcuts", "Mesh", "mesh.extrude_region_move", "Q")
    _add_keymap_item("shortcuts", "Window", "ed.redo", "Y", ctrl=True)

    preferences = bpy.context.preferences.addons.get(__package__)
    if preferences:
        _set_group_active(
            "navigation",
            preferences.preferences.enable_navigation,
        )
        _set_group_active(
            "shortcuts",
            preferences.preferences.enable_shortcuts,
        )


def _unregister_keymaps():
    for items in _KEYMAP_ITEMS.values():
        for keymap, keymap_item in reversed(items):
            keymap.keymap_items.remove(keymap_item)
        items.clear()


_CLASSES = (
    FUSIONKEYS_OT_view_cube,
    FUSIONKEYS_GIZMO_view_cube_face,
    FUSIONKEYS_GIZMO_axis_label,
    FUSIONKEYS_GIZMOGROUP_view_cube,
    FUSIONKEYS_AddonPreferences,
)


def register():
    for cls in _CLASSES:
        bpy.utils.register_class(cls)
    _register_keymaps()
    preferences = bpy.context.preferences.addons.get(__package__)
    if preferences and preferences.preferences.enable_view_cube:
        _hide_native_navigation_gizmo()


def unregister():
    _restore_native_navigation_gizmo()
    _unregister_keymaps()
    for cls in reversed(_CLASSES):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
