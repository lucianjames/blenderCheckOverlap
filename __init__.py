bl_info = {
    "name": "blenderCheckOverlaps",
    "description": "",
    "author": "Lucian James (LJ3D)",
    "version": (0, 0, 0),
    "blender": (3, 0, 0),
    "location": "3D View > Tools",
    "category": "3D View"
}


import bpy
import bmesh
from mathutils.bvhtree import BVHTree
from bpy.props import (StringProperty,
                       BoolProperty,
                       IntProperty,
                       FloatProperty,
                       FloatVectorProperty,
                       EnumProperty,
                       PointerProperty,
                       )
from bpy.types import (Panel,
                       Menu,
                       Operator,
                       PropertyGroup,
                       )
import textwrap

# ------------------------------------------------------------------------
#    Global variables
# ------------------------------------------------------------------------


overlappedObjects = []


# ------------------------------------------------------------------------
#    Scene Properties
# ------------------------------------------------------------------------

class Properties(PropertyGroup):

    filter_oneObj : BoolProperty(
        name = "Display/select overlaps for only the selected object",
        description = "",
        default = False
        )
    filter_search_oneObj : BoolProperty(
        name = "Seach for overlaps for only the selected object (faster)",
        description = "",
        default = False
        )


# ------------------------------------------------------------------------
#    Operators
# ------------------------------------------------------------------------

# Get lists of vertices and polygons of a given object/curve
def GetVertPoly(obj):
    depsgraph = bpy.context.evaluated_depsgraph_get()
    # If obj is curve, take its mesh data and store it in mesh_from_curve
    if (obj.type == 'CURVE'):
        mesh_from_curve = obj.to_mesh()
        vert = [obj.matrix_world @ v.co for v in mesh_from_curve.vertices]
        poly = [p.vertices for p in mesh_from_curve.polygons]
        return vert, poly
    else:
        # bmesh stuff is so we use geometry after modifiers
        obj_bm = bmesh.new()
        obj_bm.from_object(obj, depsgraph)
        obj_bm.verts.ensure_lookup_table()
        vert = [obj.matrix_world @ v.co for v in obj_bm.verts]
        poly = [p.vertices for p in obj.data.polygons]
        return vert, poly


# Check if two meshes have overlapping geometry
def checkOverlap(obj1, obj2):
    #get verts/polys
    vert1, poly1 = GetVertPoly(obj1)
    vert2, poly2 = GetVertPoly(obj2)
    # Create the BVH trees
    bvh1 = BVHTree.FromPolygons(vert1, poly1)
    bvh2 = BVHTree.FromPolygons(vert2, poly2)
    # Test if overlap
    # Overlap function *doesnt* return a boolean
    # It either returns some numbers or nothing
    if bvh1.overlap(bvh2):
        return True
    else:
        return False


# This is the function that runs when you click the "find overlaps" button
class WM_OT_FindOverlap(Operator):
    bl_label = "Find Overlaps"
    bl_idname = "wm.find_overlaps"
    def execute(self, context):
        scene = context.scene
        tool = scene.tool
        
        allowedObjectTypes = ['MESH', 'CURVE']
        
        # Have to clear overlappedObjects this way
        # Doing overlappedObjects = [] breaks the UI
        while len(overlappedObjects) > 0:
            overlappedObjects.pop(0)
            
        # Check every object against every other object
        if tool.filter_search_oneObj == False:
            for obj1 in bpy.data.objects:
                for obj2 in bpy.data.objects:
                    # Check obj1 and obj2 are all ok and good
                    if obj2 != obj1 and obj1.type in allowedObjectTypes and obj2.type in allowedObjectTypes:
                        # Check for overlap
                        overlap = checkOverlap(obj1, obj2)
                        # Add overlap info to overlappedObjects list
                        if overlap == True and ([obj2.name, obj1.name]) not in overlappedObjects and ([obj1.name, obj2.name]) not in overlappedObjects:
                            overlappedObjects.append([obj1.name, obj2.name])
                            
        # Check every object against one object
        if tool.filter_search_oneObj == True and scene.overlapObjFilter != None:
            obj2 = scene.overlapObjFilter
            for obj1 in bpy.data.objects:
                if scene.overlapObjFilter != obj1 and obj1.type in allowedObjectTypes and obj2.type in allowedObjectTypes:
                    # Check for overlap
                    overlap = checkOverlap(obj1, obj2)
                    # Add overlap info to overlappedObjects list
                    if overlap == True and ([obj2.name, obj1.name]) not in overlappedObjects and ([obj1.name, obj2.name]) not in overlappedObjects:
                            overlappedObjects.append([obj1.name, obj2.name])
                            
        return {'FINISHED'}


# This is the function that runs when you click the "select overlapping" button
class WM_OT_SelectOverlapping(Operator):
    bl_label = "Select Overlapping"
    bl_idname = "wm.select_overlaps"
    def execute(self, context):
        scene = context.scene
        tool = scene.tool
        
        # Deselect all objects
        for object in bpy.context.selected_objects:
            object.select_set(False)
        
        # Iterate through all ojects in overlappedObjects and set select to true
        for objects in overlappedObjects:
            # If one obj filter is on, only mark the relevant objects
            if tool.filter_oneObj == True and scene.overlapObjFilter != None:
                    # Do this by checking if either of the objects in the overlap are the selected object
                    if objects[0] == scene.overlapObjFilter.name or objects[1] == scene.overlapObjFilter.name:
                        bpy.data.objects[objects[0]].select_set(True)
                        bpy.data.objects[objects[1]].select_set(True)
            else:
                bpy.data.objects[objects[0]].select_set(True)
                bpy.data.objects[objects[1]].select_set(True)
                
        return {'FINISHED'}


# This is the function that runs when you click the "clean up unused meshes" button
class WM_OT_CleanUpMeshes(Operator):
    bl_label = "Clean up unused meshes"
    bl_idname = "wm.cleanupmeshes"
    def execute(self, context):
        for mesh in bpy.data.meshes:
            deleteMesh = True
            # Check if mesh is present in any scenes
            for iterScene in bpy.data.scenes:
                for obj in iterScene.objects[:]:
                    if obj.data == mesh:
                        deleteMesh = False # If mesh is detected in a scene, dont delete it
            if deleteMesh == True:
                bpy.data.meshes.remove(mesh) # Begone useless mesh
                
        return {'FINISHED'}


# ------------------------------------------------------------------------
#    Panel in Object Mode
# ------------------------------------------------------------------------

# UI label that does wrapping
def label_multiline(context, text, parent):
    chars = int(context.region.width / 7.5)
    wrapper = textwrap.TextWrapper(width=chars)
    text_lines = wrapper.wrap(text=text)
    for text_line in text_lines:
        parent.label(text=text_line)


# This is the UI panel
class OBJECT_PT_CustomPanel(Panel):
    bl_label = "Find Overlaps"
    bl_idname = "OBJECT_PT_custom_panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"

    @classmethod
    def poll(self,context):
        return context.mode

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        tool = scene.tool

        layout.prop(tool, "filter_oneObj")
        layout.prop(tool, "filter_search_oneObj")
        layout.prop_search(scene, "overlapObjFilter", scene, "objects")

        infobox = layout.box()
        text = "Cleaning up unused meshes fixes the problem where objects that dont exist anymore are still detected as overlapping with other objects"
        label_multiline(context=context,text=text,parent=infobox)

        layout.operator("wm.cleanupmeshes")
        layout.operator("wm.find_overlaps")
        layout.operator("wm.select_overlaps")

        box = layout.box()
        for objects in overlappedObjects:
            if tool.filter_oneObj == True and scene.overlapObjFilter != None:
                if objects[0] == scene.overlapObjFilter.name or objects[1] == scene.overlapObjFilter.name:
                    box.label(text="Overlap between {0} and {1}".format(objects[0], objects[1]))
            else:
                box.label(text="Overlap between {0} and {1}".format(objects[0], objects[1]))


# ------------------------------------------------------------------------
#    Registration
# ------------------------------------------------------------------------

classes = (
    Properties,
    WM_OT_FindOverlap,
    WM_OT_SelectOverlapping,
    WM_OT_CleanUpMeshes,
    OBJECT_PT_CustomPanel
)

def register():
    from bpy.utils import register_class
    for cls in classes:
        register_class(cls)
    bpy.types.Scene.tool = PointerProperty(type=Properties)
    bpy.types.Scene.overlapObjFilter = PointerProperty(type=bpy.types.Object)

def unregister():
    from bpy.utils import unregister_class
    for cls in reversed(classes):
        unregister_class(cls)
    del bpy.types.Scene.tool
    del bpy.types.Scene.overlapObjFilter

if __name__ == "__main__":
    register()
