# SPDX-License-Identifier: GPL-3.0-or-later

bl_info = {
    "name": "Fusion 按键与导航",
    "author": "qwejun",
    "version": (0, 5, 9),
    "blender": (5, 2, 0),
    "location": "编辑 > 偏好设置 > 插件",
    "description": "复刻 Fusion 360 风格的按键、鼠标导航和视图立方体",
    "category": "3D View",
}

import bpy
import blf
import math
import time
from bpy_extras import view3d_utils
from bpy.props import BoolProperty
from bpy.types import Gizmo, GizmoGroup, Operator, Menu
from mathutils import Matrix, Vector


_KEYMAP_ITEMS = {
    "navigation": [],
    "tab": [],
}
_NATIVE_KEYMAP_ITEMS = {
    "navigation": [],
    "tab": [],
}
_NATIVE_TAB_ITEMS = []
_NATIVE_NAV_GIZMO_STATE = {}

# Versions 0.5.3 through 0.5.5 briefly wrote shortcuts into Blender's user
# keyconfig. Those entries survive an extension update and can dispatch beside
# the current add-on keymap, so remove only the exact shortcuts this add-on
# previously created.
_LEGACY_USER_SHORTCUTS = (
    ("3D View", "view3d.move", "MIDDLEMOUSE", False, False, False, None),
    ("3D View", "view3d.rotate", "MIDDLEMOUSE", True, False, False, None),
    ("3D View", "wm.search_menu", "S", False, False, False, None),
    ("3D View", "wm.tool_set_by_id", "I", False, False, False, None),
    ("Object Mode", "transform.translate", "M", False, False, False, None),
    ("Mesh", "transform.translate", "M", False, False, False, None),
    ("Mesh", "mesh.bevel", "F", False, False, False, None),
    ("Window", "ed.redo", "Y", False, True, False, None),
)


def _set_group_active(group, active):
    for _keymap, keymap_item in _KEYMAP_ITEMS[group]:
        keymap_item.active = active
    for keymap_item, original_active in _NATIVE_KEYMAP_ITEMS[group]:
        keymap_item.active = False if active else original_active
    if group == "tab":
        _set_native_tab_items_active(False if active else None)


def _set_native_tab_items_active(active):
    """Disable (or restore) every native plain-Tab binding that competes with
    the Fusion Tab menu. Discovered at toggle time, not register time, because
    some keymaps (Object Non-modal) are materialized after startup — at
    register time the scan runs too early and items like Blender's own
    view3d.object_mode_pie_or_toggle would stay active and swallow the Tab
    release in object mode."""
    if active is False:
        _NATIVE_TAB_ITEMS.clear()
        keyconfigs = bpy.context.window_manager.keyconfigs
        for keyconfig in (keyconfigs.default, keyconfigs.user):
            if keyconfig is None:
                continue
            for keymap_name in ("3D View", "Object Non-modal", "Mesh"):
                keymap = keyconfig.keymaps.get(keymap_name)
                if keymap is None:
                    continue
                for item in keymap.keymap_items:
                    if item.idname == "view3d.fusion_smart_tab":
                        continue
                    if item.type != 'TAB' or item.shift or item.ctrl or item.alt:
                        continue
                    _NATIVE_TAB_ITEMS.append((item, item.active))
                    item.active = False
    elif active is True:
        for item, original_active in _NATIVE_TAB_ITEMS:
            try:
                item.active = original_active
            except ReferenceError:
                pass
        _NATIVE_TAB_ITEMS.clear()


def _update_navigation(self, _context):
    _set_group_active("navigation", self.enable_navigation)


def _update_tab(self, _context):
    _set_group_active("tab", self.enable_modeling_tools)


class FUSIONKEYS_AddonPreferences(bpy.types.AddonPreferences):
    bl_idname = __package__

    enable_navigation: BoolProperty(
        name="Fusion 鼠标导航",
        description="使用鼠标中键平移，Shift 加鼠标中键旋转视图",
        default=True,
        update=_update_navigation,
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

        layout.prop(self, "enable_navigation")
        navigation = layout.column(align=True)
        navigation.enabled = self.enable_navigation
        navigation.label(text="鼠标中键拖动：平移视图")
        navigation.label(text="Shift + 鼠标中键拖动：旋转视图")
        navigation.label(text="鼠标滚轮：缩放（保持 Blender 原生）")
        layout.separator()
        layout.prop(self, "enable_view_cube")
        layout.label(text="点击立方体的面：正视 / 侧视 / 顶视")
        layout.label(text="点击角：等轴测视图；Home：默认等轴测")
        layout.separator()
        layout.prop(self, "enable_modeling_tools", text="启用 Tab 模式菜单")


class FUSIONKEYS_OT_navigate(Operator):
    bl_idname = "view3d.fusion_navigate"
    bl_label = "Fusion 视图导航"
    bl_options = {'INTERNAL'}

    navigation: bpy.props.EnumProperty(items=(
        ('PAN', "平移", "平移视图"),
        ('ORBIT', "旋转", "旋转视图"),
    ))

    @classmethod
    def poll(cls, context):
        return context.area is not None and context.area.type == 'VIEW_3D'

    def invoke(self, context, event):
        if self.navigation == 'PAN':
            region_3d = context.region_data
            if region_3d is None:
                return {'CANCELLED'}
            self._start_location = region_3d.view_location.copy()
            self._start_point = view3d_utils.region_2d_to_location_3d(
                context.region,
                region_3d,
                Vector((event.mouse_region_x, event.mouse_region_y)),
                self._start_location,
            )
            context.window_manager.modal_handler_add(self)
            return {'RUNNING_MODAL'}
        return bpy.ops.view3d.rotate('INVOKE_DEFAULT')

    def modal(self, context, event):
        region_3d = context.region_data
        if event.type == 'MOUSEMOVE' and region_3d is not None:
            mouse = Vector((event.mouse_region_x, event.mouse_region_y))
            current_point = view3d_utils.region_2d_to_location_3d(
                context.region,
                region_3d,
                mouse,
                self._start_location,
            )
            region_3d.view_location = (
                self._start_location + self._start_point - current_point
            )
            context.area.tag_redraw()
            return {'RUNNING_MODAL'}
        if event.type == 'MIDDLEMOUSE' and event.value == 'RELEASE':
            return {'FINISHED'}
        if event.type in {'ESC', 'RIGHTMOUSE'}:
            if region_3d is not None:
                region_3d.view_location = self._start_location
                context.area.tag_redraw()
            return {'CANCELLED'}
        # Let wheel zoom and other viewport shortcuts pass through while the
        # Fusion pan drag is active.
        return {'PASS_THROUGH'}


class FUSIONKEYS_OT_smart_tab(Operator):
    """Tap Tab to toggle object/edit mode; hold Tab for the pie menu."""

    bl_idname = "view3d.fusion_smart_tab"
    bl_label = "Fusion Tab 模式切换"
    bl_options = {'INTERNAL'}

    _HOLD_TIME = 0.4

    @classmethod
    def poll(cls, context):
        return context.area is not None and context.area.type == 'VIEW_3D'

    def invoke(self, context, event):
        self._context = context.copy()
        self._timer = context.window_manager.event_timer_add(
            self._HOLD_TIME, window=context.window
        )
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def _finish(self, context):
        context.window_manager.event_timer_remove(self._timer)

    def _open_pie(self):
        # Opening the pie from inside modal dispatch (a TIMER event here)
        # leaves it in Blender's non-interactive fallback rendering, which
        # ignores key confirmation and item clicks. A one-shot timer runs in
        # normal operator context, producing a proper interactive pie. The
        # overrides are snapshotted up front: once this modal finishes, the
        # operator instance is destroyed and closures cannot touch it.
        overrides = {}
        for key in ("window", "area", "region"):
            value = self._context.get(key)
            if value is not None:
                overrides[key] = value

        def open_pie():
            with bpy.context.temp_override(**overrides):
                bpy.ops.wm.call_menu_pie(name=FUSIONKEYS_MT_modes.bl_idname)
            return None
        bpy.app.timers.register(open_pie, first_interval=0.0)

    def _toggle_mode(self, context):
        if context.mode == 'EDIT_MESH':
            bpy.ops.object.mode_set(mode='OBJECT')
        elif context.mode == 'OBJECT' and context.active_object is not None:
            bpy.ops.object.mode_set(mode='EDIT')

    def modal(self, context, event):
        if event.type == 'TIMER':
            # Tab held past the tap threshold: open the pie menu.
            self._finish(context)
            self._open_pie()
            return {'FINISHED'}
        if event.type == 'TAB' and event.value == 'RELEASE':
            # Quick tap: toggle object/edit mode directly.
            self._finish(context)
            self._toggle_mode(context)
            return {'FINISHED'}
        if event.type == 'ESC':
            self._finish(context)
            return {'CANCELLED'}
        return {'PASS_THROUGH'}


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


class FUSIONKEYS_OT_toggle_object_edit_mode(Operator):
    bl_idname = "object.fusion_toggle_object_edit_mode"
    bl_label = "切换物体 / 编辑模式"
    bl_description = "在物体模式和编辑模式之间切换"
    bl_options = {'REGISTER'}

    @classmethod
    def poll(cls, context):
        return context.active_object is not None and context.active_object.type == 'MESH'

    def execute(self, context):
        if context.mode == 'EDIT_MESH':
            bpy.ops.object.mode_set(mode='OBJECT')
        elif context.mode == 'OBJECT':
            bpy.ops.object.mode_set(mode='EDIT')
        return {'FINISHED'}


class FUSIONKEYS_OT_toggle_edit_option(Operator):
    bl_idname = "mesh.fusion_toggle_edit_option"
    bl_label = "Fusion 编辑选项"
    bl_options = {'REGISTER', 'UNDO'}

    option: bpy.props.EnumProperty(items=(
        ('OCCLUDE', "遮挡选择", "切换只选择可见面/穿透选择"),
    ))

    @classmethod
    def poll(cls, context):
        return context.active_object is not None and context.active_object.type == 'MESH'

    def execute(self, context):
        if context.mode != 'EDIT_MESH':
            bpy.ops.object.mode_set(mode='EDIT')
        space = context.space_data
        if hasattr(space, "shading") and hasattr(space.shading, "show_xray"):
            space.shading.show_xray = not space.shading.show_xray
        return {'FINISHED'}


class FUSIONKEYS_MT_modes(Menu):
    bl_idname = "FUSIONKEYS_MT_modes"
    bl_label = "Fusion 模式菜单"

    def draw(self, context):
        pie = self.layout.menu_pie()
        mode_toggle = pie.row()
        is_mesh = context.active_object is not None and context.active_object.type == 'MESH'
        mode_toggle.enabled = is_mesh and context.mode in {'OBJECT', 'EDIT_MESH'}
        if context.mode == 'EDIT_MESH':
            mode_toggle.operator(
                "object.fusion_toggle_object_edit_mode",
                text="返回物体模式",
                icon='OBJECT_DATA',
            )
        else:
            mode_toggle.operator(
                "object.fusion_toggle_object_edit_mode",
                text="进入编辑模式",
                icon='EDITMODE_HLT',
            )
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


def _copy_default_keymap_items(keymap_name, target_keymap):
    """Fill a fresh user keymap with Blender's default items.

    A partial user keymap would shadow the entire default keymap in the active
    keyconfig, silently removing every native binding it holds (wheel zoom,
    view axis shortcuts, ...). Blender itself materializes a full copy whenever
    a user edits a keymap, so mirror that here before adding add-on entries.
    """
    default_keymap = bpy.context.window_manager.keyconfigs.default.keymaps.get(
        keymap_name
    )
    if default_keymap is None:
        return
    for item in default_keymap.keymap_items:
        try:
            new_item = target_keymap.keymap_items.new(
                item.idname,
                item.type,
                item.value,
                shift=item.shift,
                ctrl=item.ctrl,
                alt=item.alt,
                oskey=item.oskey,
                key_modifier=item.key_modifier,
                direction=item.direction,
                repeat=item.repeat,
            )
            new_item.active = item.active
            for name in item.properties.keys():
                setattr(new_item.properties, name, item.properties[name])
        except (RuntimeError, AttributeError, TypeError):
            # A default entry that cannot be mirrored must not abort the
            # remaining copies; the default keyconfig still dispatches it.
            continue


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
    # Blender 5.2 does not dispatch add-on keyconfig entries for these
    # built-in viewport events, so the entries must live in the user layer.
    # To keep that from shadowing native bindings, a missing user keymap is
    # first filled with the full default set (see _copy_default_keymap_items).
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
        _copy_default_keymap_items(keymap_name, keymap)

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


def _menu_name(item):
    try:
        return item.properties.name
    except (AttributeError, TypeError):
        return ""


def _remove_legacy_user_keymaps():
    """Remove only shortcuts written by older Fusion Navigation releases."""
    keyconfig = bpy.context.window_manager.keyconfigs.user
    if keyconfig is None:
        return

    touched = set()
    for keymap in keyconfig.keymaps:
        for item in list(keymap.keymap_items):
            if item.idname == "view3d.fusion_navigate" or item.idname.startswith(
                "view3d.fusion_smart_tab"
            ):
                keymap.keymap_items.remove(item)
                touched.add(keymap.name)
                continue
            if (item.idname == "wm.call_menu_pie"
                    and _menu_name(item).startswith("FUSIONKEYS_MT_")):
                keymap.keymap_items.remove(item)
                touched.add(keymap.name)
                continue

            signature = (
                keymap.name,
                item.idname,
                item.type,
                bool(item.shift),
                bool(item.ctrl),
                bool(item.alt),
                None,
            )
            if signature in _LEGACY_USER_SHORTCUTS:
                keymap.keymap_items.remove(item)

    # Version 0.5.6 created a partial user "3D View" keymap that shadowed the
    # whole default 3D View keymap (breaking wheel zoom). Drop it once emptied;
    # a keymap the user customized still holds their own items and is kept.
    for keymap_name in touched:
        keymap = keyconfig.keymaps.get(keymap_name)
        if keymap is not None and len(keymap.keymap_items) == 0:
            try:
                keyconfig.keymaps.remove(keymap)
            except (RuntimeError, ReferenceError):
                pass

    # Version 0.5.5 disabled Blender's plain Tab mode switch. Re-enable only
    # that exact native command; the add-on keymap will take priority while the
    # extension is enabled.
    for keymap_name in ("Object Non-modal", "Mesh"):
        keymap = keyconfig.keymaps.get(keymap_name)
        if keymap is None:
            continue
        for item in keymap.keymap_items:
            if (item.idname == "object.mode_set" and item.type == 'TAB'
                    and not item.shift and not item.ctrl and not item.alt):
                item.active = True


def _capture_native_keymap_conflicts():
    """Remember the three native actions replaced by this extension."""
    keyconfigs = bpy.context.window_manager.keyconfigs
    for keyconfig in (keyconfigs.default, keyconfigs.user):
        if keyconfig is None:
            continue
        for keymap in keyconfig.keymaps:
            for item in keymap.keymap_items:
                plain_middle_rotate = (
                    keymap.name == "3D View"
                    and item.idname == "view3d.rotate"
                    and item.type == 'MIDDLEMOUSE'
                    and not item.shift and not item.ctrl and not item.alt
                )
                shift_middle_move = (
                    keymap.name == "3D View"
                    and item.idname == "view3d.move"
                    and item.type == 'MIDDLEMOUSE'
                    and item.shift and not item.ctrl and not item.alt
                )
                plain_tab = (
                    keymap.name in {"3D View", "Object Non-modal", "Mesh"}
                    and item.type == 'TAB'
                    and not item.shift and not item.ctrl and not item.alt
                )
                if plain_middle_rotate or shift_middle_move:
                    _NATIVE_KEYMAP_ITEMS["navigation"].append((item, item.active))
                elif plain_tab:
                    _NATIVE_KEYMAP_ITEMS["tab"].append((item, item.active))


def _restore_native_keymap_conflicts():
    for items in _NATIVE_KEYMAP_ITEMS.values():
        for item, original_active in items:
            try:
                item.active = original_active
            except ReferenceError:
                pass
        items.clear()


def _register_keymaps():
    _remove_legacy_user_keymaps()
    _capture_native_keymap_conflicts()
    # Fusion swaps Blender's default middle-mouse actions.
    _add_keymap_item(
        "navigation",
        "3D View",
        "view3d.fusion_navigate",
        "MIDDLEMOUSE",
        space_type="VIEW_3D",
        properties={"navigation": 'PAN'},
    )
    _add_keymap_item(
        "navigation",
        "3D View",
        "view3d.fusion_navigate",
        "MIDDLEMOUSE",
        space_type="VIEW_3D",
        shift=True,
        properties={"navigation": 'ORBIT'},
    )
    _add_keymap_item(
        "tab",
        "3D View",
        "view3d.fusion_smart_tab",
        "TAB",
        space_type="VIEW_3D",
    )

    preferences = bpy.context.preferences.addons.get(__package__)
    if preferences:
        _set_group_active("navigation", preferences.preferences.enable_navigation)
        _set_group_active("tab", preferences.preferences.enable_modeling_tools)


def _unregister_keymaps():
    _restore_native_keymap_conflicts()
    _set_native_tab_items_active(True)
    for items in _KEYMAP_ITEMS.values():
        for keymap, keymap_item in reversed(items):
            try:
                keymap.keymap_items.remove(keymap_item)
            except (ReferenceError, RuntimeError, UnicodeError):
                # Blender may already have removed an extension keymap during
                # reload or extension installation. Unregister must remain
                # idempotent in that case.
                pass
        items.clear()


_CLASSES = (
    FUSIONKEYS_OT_navigate,
    FUSIONKEYS_OT_smart_tab,
    FUSIONKEYS_OT_view_cube,
    FUSIONKEYS_OT_set_selection_mode,
    FUSIONKEYS_OT_toggle_object_edit_mode,
    FUSIONKEYS_OT_toggle_edit_option,
    FUSIONKEYS_MT_modes,
    FUSIONKEYS_GIZMO_view_cube_face,
    FUSIONKEYS_GIZMO_axis_label,
    FUSIONKEYS_GIZMOGROUP_view_cube,
    FUSIONKEYS_AddonPreferences,
)


def _deferred_native_tab_scan():
    """Re-run the native Tab disable once startup keymaps have materialized."""
    preferences = bpy.context.preferences.addons.get(__package__)
    if preferences and preferences.preferences.enable_modeling_tools:
        _set_native_tab_items_active(False)
    return None


def register():
    for cls in _CLASSES:
        bpy.utils.register_class(cls)
    _register_keymaps()
    preferences = bpy.context.preferences.addons.get(__package__)
    if preferences and preferences.preferences.enable_view_cube:
        _hide_native_navigation_gizmo()
    bpy.app.timers.register(_deferred_native_tab_scan, first_interval=1.5)


def unregister():
    _restore_native_navigation_gizmo()
    _unregister_keymaps()
    for cls in reversed(_CLASSES):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
