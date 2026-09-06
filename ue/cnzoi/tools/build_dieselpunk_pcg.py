"""Run through UE ProgrammaticToolset after creating PCG_DieselpunkCityBlock.

Builds a native, parameter-driven editor PCG graph. Asset creation and graph
execution are intentionally separate MCP calls. Existing graph is inspected
before authoring; this script is for the initial empty graph only.
"""
import json

GRAPH = {'refPath':'/Game/PCSP/City/PCG/PCG_DieselpunkCityBlock.PCG_DieselpunkCityBlock'}

def pcg(tool, args):
    return execute_tool('PCGToolset.PCGToolset.' + tool, json.dumps(args))['returnValue']

def run():
    structure = pcg('GetGraphStructure', {'graph':GRAPH})
    if len(structure['nodes']) != 2:
        raise RuntimeError('Expected an empty graph; inspect before modifying existing nodes.')
    definitions = [
        ('ActorClass','SoftClassPath',{'refPath':'/Game/dieselpunk/Actors/KB3D_DPK_BldgSMApartments_A.KB3D_DPK_BldgSMApartments_A_C'},'Building Blueprint generated on each lot. Keep its footprint smaller than LotSpacing.'),
        ('AreaHalfSize','Vector',{'x':4000,'y':5000,'z':0},'Half extents in cm. Z=0 creates a ground plane. Independent of volume scale.'),
        ('LotSpacing','Vector',{'x':4000,'y':5000,'z':100},'Grid cell dimensions in cm. All components must be positive.'),
        ('FillRatio','Float',1.0,'Fraction of lots to fill, from 0 to 1.'),
        ('LayoutSeed','Integer32',42,'Seed for occupancy and transform variation.'),
        ('Facing','Rotator',{'pitch':0,'yaw':0,'roll':0},'Local building orientation. Use yaw 0, 90, 180 or 270 for streets.'),
        ('JitterMin','Vector',{'x':0,'y':0,'z':0},'Minimum local offset in cm. Keep Z zero for ground contact.'),
        ('JitterMax','Vector',{'x':0,'y':0,'z':0},'Maximum local offset in cm. Reserve enough space for building footprints.'),
        ('MinScale','Vector',{'x':1,'y':1,'z':1},'Minimum uniform scale. X is used for all axes.'),
        ('MaxScale','Vector',{'x':1,'y':1,'z':1},'Maximum uniform scale. X is used for all axes.'),
        ('GeneratedLabel','String','PCG_City_Building','Label prefix for generated actors. Regenerate to apply.'),
        ('SpatiallyLoaded','Boolean',False,'Keep false for this always-loaded portfolio layout. Enable only with a configured World Partition streaming workflow.')
    ]
    pcg('SetGraphParams', {'graph':GRAPH,'params':[{'name':n,'type':t,'description':d,'containerType':'None','defaultValueJson':json.dumps(v)} for n,t,v,d in definitions]})
    nodes = {}
    def add(key, native, params, x, y, comment=''):
        nodes[key] = pcg('AddNode',{'graph':GRAPH,'nativeNodeType':native,'nodeName':key,'jsonParams':json.dumps(params),'nodeTitle':key,'nodeComment':comment,'xPositionIdx':x,'yPositionIdx':y})
    def wire(source,pin,destination,input_pin):
        pcg('ConnectNodePins',{'fromNode':nodes[source],'fromPinLabel':pin,'toNode':nodes[destination],'toPinLabel':input_pin})
    add('Lots','Create Points Grid',{'coordinateSpace':'LocalComponent','bCullPointsOutsideVolume':False,'pointPosition':'CellCenter'},0,0,'AreaHalfSize and LotSpacing define the editable grid. Move the PCG actor to move the district.')
    add('Occupancy','Random Choice',{'bFixedMode':False,'ratio':1.0,'bOutputDiscardedEntries':False},500,0)
    add('Variation','Transform Points',{'bUniformScale':True},1000,0)
    add('BuildingClass','Add Attribute',{'bCopyAllAttributes':True},1500,0)
    add('StreamingFlags','Add Attribute',{'bCopyAllAttributes':True},2000,0)
    add('Buildings','Spawn Actor',{'option':'NoMerging','bSpawnByAttribute':True,'spawnAttribute':'ActorClass','attachOptions':'InFolder','bInheritActorTags':False,'tagsToAddOnActors':['PCSP_City_PCG'],'actorLabel':'PCG_City_Building','spawnedActorPropertyOverrideDescriptions':[{'inputSource':'SpatiallyLoaded','propertyTarget':'bIsSpatiallyLoaded'}]},2500,0,'Generated actors are owned by PCG. Edit the volume parameters, then Generate; use Cleanup to remove output.')
    for i,(name,typ,value,description) in enumerate(definitions):
        add('Param_' + name,'Get Graph Parameter',{'propertyPath':name,'outputAttributeName':name},(i//3)*500,-700+(i%3)*180)
    for name,dest,pins in [('AreaHalfSize','Lots',['GridExtents']),('LotSpacing','Lots',['CellSize']),('FillRatio','Occupancy',['Ratio']),('LayoutSeed','Occupancy',['Seed']),('Facing','Variation',['RotationMin','RotationMax']),('JitterMin','Variation',['OffsetMin']),('JitterMax','Variation',['OffsetMax']),('MinScale','Variation',['ScaleMin']),('MaxScale','Variation',['ScaleMax']),('GeneratedLabel','Buildings',['ActorLabel'])]:
        for pin in pins:
            wire('Param_' + name,'Out',dest,pin)
    wire('Param_LayoutSeed','Out','Variation','Seed')
    wire('Param_ActorClass','Out','BuildingClass','Attributes')
    wire('Lots','Out','Occupancy','In')
    wire('Occupancy','Chosen','Variation','In')
    wire('Variation','Out','BuildingClass','In')
    wire('Param_SpatiallyLoaded','Out','StreamingFlags','Attributes')
    wire('BuildingClass','Out','StreamingFlags','In')
    wire('StreamingFlags','Out','Buildings','In')
    nodes['Output'] = {'refPath':GRAPH['refPath'] + ':DefaultOutputNode'}
    pcg('RepositionNode',{'node':nodes['Output'],'xPositionIdx':3000,'yPositionIdx':0})
    pcg('RepositionNode',{'node':{'refPath':GRAPH['refPath']+':DefaultInputNode'},'xPositionIdx':-400,'yPositionIdx':200})
    wire('Buildings','Out','Output','Out')
    pcg('SetGraphDescription',{'graph':GRAPH,'description':'Editable Dieselpunk city lots. Select a City_PCG_* volume and override graph parameters. Dimensions are centimeters, AreaHalfSize is half extent, volume scale only shows its authoring bounds. FillRatio controls occupancy. ActorClass uses a Blueprint generated class. No runtime generation is required.'})
    return {'graph':GRAPH,'structure':pcg('GetGraphStructure',{'graph':GRAPH})}
