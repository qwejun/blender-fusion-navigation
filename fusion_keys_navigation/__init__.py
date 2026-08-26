# SPDX-License-Identifier: GPL-3.0-or-later

bl_info = {
    "name": "Fusion 按键与导航",
    "author": "qwejun",
    "version": (0, 5, 5),
    "blender": (5, 2, 0),
    "location": "编辑 > 偏好设置 > 插件",
    "description": "复刻 Fusion 360 风格的按键、鼠标导航和视图立方体",
    "category": "3D View",
}

import bpy
import blf
import math
from bpy.props import BoolProperty
from bpy.types import Gizmo, GizmoGroup, Operator, Menu
from mathutils import Matrix, Vector


_KEYMAP_ITEMS = {
    "tab": [],
}
_NATIVE_NAV_GIZMO_STATE = {}
_CONFLICTING_KEYMAP_STATE = []


def _set_group_active(group, active):
    for _keymap, keymap_item in _KEYMAP_ITEMS[group]:
        keymap_item.active = active


def _update_tab(self, _context):
    _set_group_active("tab", self.enable_modeling_tools)


class FUSIONKEYS_AddonPreferences(bpy.types.AddonPreferences):
    bl_idname = __package__

    enable_navigation: BoolProperty(
        name="Fusion 鼠标导航",
        description="使用鼠标中键平移，Shift 加鼠标中键旋转视图",
        default=True,
        update=None,
    )
    enable_shortcuts: BoolProperty(
        name="Fusion 快捷键",
        description="启用在 Blender 中具有明确对应功能的 Fusion 常用快捷键",
        default=True,
        update=None,
    )
    enable_view_cube: BoolProperty(
        name="Fusion 视图立方体",
        description="在 3D 视图右上角显示可点击的 Fusion 风格视图立方体",
        default=True,
        update=lambda self, _context: _update_view_cube(self),
    )
    enable_modeling_tools: BoolProperty(
        name="Fusion 建模辅助",
        description="启用 3D 视图中的 Tab 模式菜单",
        default=True,
        update=_update_tab,
    )

    def draw(self, _context):
        layout = self.layout

        layout.label(text="本插件只接管 3D 视图中的 Tab 模式菜单")
        layout.label(text="其它快捷键和导航全部保持 Blender 原生")
        layout.separator()
        layout.prop(self, "enable_view_cube")
        layout.label(text="点击立方体的面：正视 / 侧视 / 顶视")
        layout.label(text="点击角：等轴测视图；Home：默认等轴测")
        layout.separator()
        layout.prop(self, "enable_modeling_tools", text="启用 Tab 模式菜单")


class FUSIONKEYS_OT_set_selection_mode(Operator):
    bl_idname = "mesh.fusion_set_selection_mode"
    bl_label = "Fusion 选择模式"
    bl_options = {'REGISTER', 'UNDO'}

    mode: bpy.props.EnumProperty(items=(
        ('VERT', "顶点", "顶点选择"),
        ('EDGE', "边", "边选择"),
        ('FACE', "面", "面选择"),
    ))

    @classmethod
    def poll(cls, context):
        return context.active_object is not None and context.active_object.type == 'MESH'

    def execute(self, context):
        if context.mode != 'EDIT_MESH':
            bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_mode(type=self.mode)
        return {'FINISHED'}


class FUSIONKEYS_OT_set_object_mode(Operator):
    """Enter Object Mode without passing an invalid request to Blender."""

    bl_idname = "object.fusion_set_object_mode"
    bl_label = "对象模式"
    bl_options = {'REGISTER'}

    @classmethod
    def poll(cls, context):
        return context.active_object is not None

    def execute(self, context):
        # A mesh can be visible without being the active object (for example
        # after deselection). In that case Object Mode is already the only
        # meaningful target, so finish quietly instead of showing an error.
        if context.active_object is None:
            return {'FINISHED'}
        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        return {'FINISHED'}


class FUSIONKEYS_OT_toggle_edit_option(Operator):
    bl_idname = "mesh.fusion_toggle_edit_option"
    bl_label = "Fusion 编辑选项"
    bl_options = {'REGISTER', 'UNDO'}

    option: bpy.props.EnumProperty(items=(
        ('OCCLUDE', "遮挡选择", "切换只选择可见面/穿透选择"),
        ('MERGE', "自动合并", "切换编辑模式自动合并顶点"),
    ))

    @classmethod
    def poll(cls, context):
        return context.active_object is not None and context.active_object.type == 'MESH'

    def execute(self, context):
        if context.mode != 'EDIT_MESH':
            bpy.ops.object.mode_set(mode='EDIT')
        space = context.space_data
        if self.option == 'OCCLUDE':
            if hasattr(space, "shading") and hasattr(space.shading, "show_xray"):
                space.shading.show_xray = not space.shading.show_xray
        else:
            ts = context.scene.tool_settings
            ts.use_mesh_automerge = not ts.use_mesh_automerge
        return {'FINISHED'}


class FUSIONKEYS_OT_surface_slide(Operator):
    bl_idname = "mesh.fusion_surface_slide"
    bl_label = "Fusion 表面滑移"
    bl_description = "沿现有网格表面滑移选中的顶点"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.active_object is not None and context.active_object.type == 'MESH'

    def invoke(self, context, event):
        # Blender's native vertex slide is the safest topology-preserving
        # surface adjustment available without replacing the mesh data.
        return bpy.ops.transform.vert_slide('INVOKE_DEFAULT')

    def execute(self, context):
        return bpy.ops.transform.vert_slide('EXEC_DEFAULT')


class FUSIONKEYS_MT_modes(Menu):
    bl_idname = "FUSIONKEYS_MT_modes"
    bl_label = "Fusion 模式菜单"

    def draw(self, context):
        pie = self.layout.menu_pie()
        object_mode = pie.row()
        object_mode.enabled = context.active_object is not None
        object_mode.operator("object.fusion_set_object_mode", text="对象", icon='OBJECT_DATA')
        if context.active_object is not None and context.active_object.type == 'MESH':
            pie.operator("mesh.fusion_set_selection_mode", text="顶点", icon='VERTEXSEL').mode = 'VERT'
            pie.operator("mesh.fusion_set_selection_mode", text="边", icon='EDGESEL').mode = 'EDGE'
            pie.operator("mesh.fusion_set_selection_mode", text="面", icon='FACESEL').mode = 'FACE'
        pie.operator("ed.undo", text="撤销", icon='LOOP_BACK')
        restore_view = pie.operator("view3d.view_all", text="恢复视角", icon='HOME')
        restore_view.center = True
        if context.mode == 'EDIT_MESH' and context.active_object is not None:
            pie.operator("mesh.fusion_toggle_edit_option", text="遮挡选择", icon='XRAY').option = 'OCCLUDE'
        else:
            pie.separator()
        region_3d = getattr(context.space_data, "region_3d", None)
        is_perspective = (
            True if region_3d is None
            else region_3d.view_perspective == 'PERSP'
        )
        pie.operator(
            "view3d.view_persportho",
            text="切换到正交" if is_perspective else "切换到透视",
        )


class FUSIONKEYS_MT_modeling(Menu):
    bl_idname = "FUSIONKEYS_MT_modeling"
    bl_label = "Fusion 建模菜单"

    def draw(self, context):
        pie = self.layout.menu_pie()
        is_edit = context.mode == 'EDIT_MESH'

        # East: extrusion submenu, kept on Blender's native operators.
        extrude = pie.row()
        extrude.enabled = is_edit
        extrude.menu("FUSIONKEYS_MT_extrude", text="拉伸 / 推拉", icon='EXTRUDE_REGION')
        pie.menu("FUSIONKEYS_MT_views", text="视图", icon='VIEW3D')
        pie.menu("FUSIONKEYS_MT_snapping", text="吸附", icon='SNAP_ON')
        pie.menu("FUSIONKEYS_MT_modes", text="模式", icon='VERTEXSEL')
        pie.operator("ed.undo", text="撤销", icon='LOOP_BACK')
        restore_view = pie.operator("view3d.view_all", text="恢复视角", icon='HOME')
        restore_view.center = True


class FUSIONKEYS_MT_selection(Menu):
    bl_idname = "FUSIONKEYS_MT_selection"
    bl_label = "选择模式"

    def draw(self, context):
        layout = self.layout
        if context.mode != 'EDIT_MESH':
            layout.operator("object.fusion_set_object_mode", text="对象", icon='OBJECT_DATA')
        row = layout.row()
        row.enabled = context.mode == 'EDIT_MESH' and context.active_object is not None
        row.operator("mesh.fusion_set_selection_mode", text="顶点", icon='VERTEXSEL').mode = 'VERT'
        row = layout.row()
        row.enabled = context.mode == 'EDIT_MESH' and context.active_object is not None
        row.operator("mesh.fusion_set_selection_mode", text="边", icon='EDGESEL').mode = 'EDGE'
        row = layout.row()
        row.enabled = context.mode == 'EDIT_MESH' and context.active_object is not None
        row.operator("mesh.fusion_set_selection_mode", text="面", icon='FACESEL').mode = 'FACE'


class FUSIONKEYS_MT_extrude(Menu):
    bl_idname = "FUSIONKEYS_MT_extrude"
    bl_label = "拉伸 / 推拉"

    def draw(self, _context):
        layout = self.layout
        layout.operator("mesh.extrude_region_move", text="挤出区域", icon='EXTRUDE_REGION')
        layout.operator("mesh.extrude_region_shrink_fatten", text="沿法线挤出", icon='NORMALS_FACE')
        layout.operator("mesh.extrude_manifold", text="挤出并集", icon='MOD_SOLIDIFY')
        layout.operator("mesh.inset", text="内插面", icon='INSET_FACES')


class FUSIONKEYS_MT_views(Menu):
    bl_idname = "FUSIONKEYS_MT_views"
    bl_label = "视图"

    def draw(self, context):
        layout = self.layout
        for direction, label in (
            ('FRONT', "前视图"), ('BACK', "后视图"),
            ('LEFT', "左视图"), ('RIGHT', "右视图"),
            ('TOP', "顶视图"), ('BOTTOM', "底视图"),
            ('ISO', "等轴测视图"),
        ):
            op = layout.operator("view3d.fusion_view_cube", text=label)
            op.direction = direction


class FUSIONKEYS_MT_snapping(Menu):
    bl_idname = "FUSIONKEYS_MT_snapping"
    bl_label = "吸附"

    def draw(self, context):
        layout = self.layout
        ts = context.scene.tool_settings
        layout.prop(ts, "use_snap", text="启用吸附")
        layout.prop(ts, "snap_elements", text="吸附元素")
        layout.prop(ts, "snap_target", text="吸附目标")
        layout.prop(ts, "use_snap_align_rotation", text="对齐旋转")


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
            ('TOP', "顶", (0, 0, 1), ((-1, -1, 1), (1, -1, 1), (1, 1, 1), (-1, 1, 1))),
            ('BOTTOM', "底", (0, 0, -1), ((-1, 1, -1), (1, 1, -1), (1, -1, -1), (-1, -1, -1))),
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
    # Blender 5.2 does not reliably dispatch extension keymaps from
    # keyconfigs.addon. Store this single opt-in shortcut in the user
    # keyconfig so it participates in the active keymap immediately.
    keyconfig = bpy.context.window_manager.keyconfigs.user
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


def _remove_stale_modeling_keymaps():
    """Remove shortcuts left by older versions, keeping Blender defaults."""
    for keyconfig in (bpy.context.window_manager.keyconfigs.user,
                      bpy.context.window_manager.keyconfigs.addon):
        if keyconfig is None:
            continue
        for keymap in keyconfig.keymaps:
            for item in list(keymap.keymap_items):
                try:
                    name = item.properties.name
                except (AttributeError, TypeError):
                    name = ""
                is_old_plugin_shortcut = keyconfig == bpy.context.window_manager.keyconfigs.addon and (
                    (keymap.name == "3D View" and item.idname in {"view3d.move", "view3d.rotate"}
                     and item.type == "MIDDLEMOUSE")
                    or (keymap.name == "3D View" and item.idname == "wm.search_menu" and item.type == "S")
                    or (keymap.name == "3D View" and item.idname == "wm.tool_set_by_id" and item.type == "I")
                    or (keymap.name in {"Object Mode", "Mesh"} and item.idname == "transform.translate" and item.type == "M")
                    or (keymap.name == "Mesh" and item.idname == "mesh.bevel" and item.type == "F")
                    or (keymap.name == "Window" and item.idname == "ed.redo" and item.type == "Y" and item.ctrl)
                )
                if name.startswith("FUSIONKEYS_MT_") or is_old_plugin_shortcut:
                    keymap.keymap_items.remove(item)


def _disable_conflicting_alt_q():
    """Let Alt+Q open our menu instead of Blender's Transfer Mode command."""
    _CONFLICTING_KEYMAP_STATE.clear()
    for keyconfig in (bpy.context.window_manager.keyconfigs.default,
                      bpy.context.window_manager.keyconfigs.user):
        if keyconfig is None:
            continue
        for keymap in keyconfig.keymaps:
            if keymap.name != "Object Non-modal":
                continue
            for item in keymap.keymap_items:
                if item.idname != "object.transfer_mode":
                    continue
                if item.type == 'Q' and item.alt:
                    _CONFLICTING_KEYMAP_STATE.append((item, item.active))
                    item.active = False


def _disable_conflicting_tab():
    """Let Tab open the Modes pie instead of Blender's mode toggle."""
    for keyconfig in (bpy.context.window_manager.keyconfigs.default,
                      bpy.context.window_manager.keyconfigs.user):
        if keyconfig is None:
            continue
        for keymap in keyconfig.keymaps:
            if keymap.name not in {"Object Non-modal", "Mesh", "3D View"}:
                continue
            for item in keymap.keymap_items:
                if (item.type == 'TAB' and not item.shift and not item.ctrl and not item.alt
                        and item.idname != "wm.call_menu_pie"):
                    _CONFLICTING_KEYMAP_STATE.append((item, item.active))
                    item.active = False


def _restore_conflicting_alt_q():
    for item, active in _CONFLICTING_KEYMAP_STATE:
        try:
            item.active = active
        except ReferenceError:
            pass
    _CONFLICTING_KEYMAP_STATE.clear()


def _register_keymaps():
    _remove_stale_modeling_keymaps()
    _disable_conflicting_tab()
    _add_keymap_item(
        "tab",
        "3D View",
        "wm.call_menu_pie",
        "TAB",
        space_type="VIEW_3D",
        properties={"name": FUSIONKEYS_MT_modes.bl_idname},
    )

    preferences = bpy.context.preferences.addons.get(__package__)
    if preferences:
        _set_group_active("tab", preferences.preferences.enable_modeling_tools)


def _unregister_keymaps():
    for items in _KEYMAP_ITEMS.values():
        for keymap, keymap_item in reversed(items):
            try:
                keymap.keymap_items.remove(keymap_item)
            except (ReferenceError, RuntimeError):
                # Blender may already have removed an extension keymap during
                # reload or extension installation. Unregister must remain
                # idempotent in that case.
                pass
        items.clear()


_CLASSES = (
    FUSIONKEYS_OT_view_cube,
    FUSIONKEYS_OT_set_selection_mode,
    FUSIONKEYS_OT_set_object_mode,
    FUSIONKEYS_OT_toggle_edit_option,
    FUSIONKEYS_OT_surface_slide,
    FUSIONKEYS_MT_modes,
    FUSIONKEYS_MT_modeling,
    FUSIONKEYS_MT_selection,
    FUSIONKEYS_MT_extrude,
    FUSIONKEYS_MT_views,
    FUSIONKEYS_MT_snapping,
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
    _restore_conflicting_alt_q()
    _unregister_keymaps()
    for cls in reversed(_CLASSES):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
