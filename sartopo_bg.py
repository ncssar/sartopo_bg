from sartopo_python import SartopoSession
import logging
import re
import time
import sys
import json
from os import path

# To redefine basicConfig, per stackoverflow.com/questions/12158048
# Remove all handlers associated with the root logger object.
for handler in logging.root.handlers[:]:
    logging.root.removeHandler(handler)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler('bg.log','w'),
        logging.StreamHandler(sys.stdout)
    ]
)

# do not register the callbacks until after the initial processing; that way we
#  can be sure to process existing assignments first

# assignments - dictionary of dictionaries of assignment data; each assignment sub-dictionary
#   is created upon processing of the first object that appears to be related to the assigment,
#   based on title ('AA101' for assignment objects, or 'AA101a' for lines, possibly including space(s))
# NOTE - we really want to be able to recreate the ID associations at runtime (what target map
#   object corresponds to what source map object) rather than relying on a correspondence file,
#   but that would require a place for metadata on the target map objects.  Maybe the target map
#   details / description field could be used for this?  Any new field added here just gets deleted
#   by sartopo.  How important is it to keep this ID correspondence?  IS title sufficient?
#  key = assignment title (name and number; i.e. we want one dict entry per pairing/'outing')
#  val = dictionary
#     bid - id of boundary object (in the target map)
#     fid - id of folder object (in the target map)
#     sid - id of the assignment object (in the SOURCE map)
#     cids - list of ids of associated clues (in the target map)
#     tids - list of ids of associated tracks (in the target map)
#     utids - list of uncropped track ids (since the track may be processed before the boundary)

# sourceMapID='V80'
# targetMapID='0SD' # must already be a saved map
sourceMapID='9B1'
targetMapID='UG1' # must already be a saved map
fileNameBase=sourceMapID+'_'+targetMapID
corrFileName=fileNameBase+'.json'
assignmentsFileName=fileNameBase+'_assignments.json'

def writeAssignmentsFile():
    # write the correspondence file
    with open(assignmentsFileName,'w') as assignmentsFile:
        assignmentsFile.write(json.dumps(assignments,indent=3))

# open a session on the target map first, since nocb definition checks for it
try:
    sts2=SartopoSession('localhost:8080',targetMapID,sync=False,syncTimeout=10,syncDumpFile='../../'+targetMapID+'.txt')
except:
    sys.exit()

assignments={} # assignments dictionary
assignments_init={} # pre-filtered assignments dictionary (read from file on startup)

fids={} # folder IDs

# correspondence dictionary (and json file) - serves two purposes:
# 1. crash recovery - on startup, the task is to import features from the source map
#      which don't have any correspondence in the target map; this avoids the need
#      to delete all features from the target map before startup
# 2. applying source map edits to the target map - when a source map feature is
#      edited or deleted, the correspondence dictionary will determine what target map
#      feature(s) will receive the same edit/deletion

# record pre-cropped and also post-cropped tracks in the correspondence dictionary;
#  the dictionary consumers will need to check to see if each entry exists before applying
#  any action.

corr={} # correspondence dictionary: key=source-map-ID, val=list-of-target-map-IDs
corr_init={} # pre-fitlered correspondence dictionary (read from file on startup)

if path.exists(corrFileName):
    with open(corrFileName,'r') as corrFile:
        logging.info('reading correlation file')
        corr_init=json.load(corrFile)
        logging.info(json.dumps(corr_init,indent=3))

# remove correspondence entries for objects that no longer exist in the target map
# (do not edit an object while iterating over it - that always gives bizarre results)
tids=sum(sts2.mapData['ids'].values(),[])
logging.info('list of all sts2 ids:'+str(tids))
# sidsToRemove=[]
# for sid in corr.keys():
#     logging.info('checking sid '+sid+':'+str(corr[sid]))
#     for tid in corr[sid]:
#         logging.info(' checking tid '+tid)
#         if tid in tids:
#             logging.info('  not in target map; removing')
#             corr[sid].remove(tid)
#     if corr[sid]==[]:
#         logging.info(' sid '+sid+' no longer has any correspondence; will be removed from correlation dictionary')
#         sidsToRemove.append(sid)
for sid in corr_init.keys():
    idListToAdd=[id for id in corr_init[sid] if id in tids]
    if idListToAdd!=[]:
        corr[sid]=idListToAdd
# for sidToRemove in sidsToRemove:
#     del corr[sidToRemove]
# write the correspondence file
with open(corrFileName,'w') as corrFile:
    corrFile.write(json.dumps(corr,indent=3))
logging.info('correlation table after pruning:')
logging.info(json.dumps(corr,indent=3))

# restart handling: read the assignments file (if any)
if path.exists(assignmentsFileName):
    with open(assignmentsFileName,'r') as assignmentsFile:
        logging.info('reading assignments file')
        assignments_init=json.load(assignmentsFile)
        logging.info(json.dumps(assignments_init,indent=3))

# then get rid of id's that don't exist in the target map
for a in assignments_init:
    # create the assigmment entry even if the corresponding source id
    #  does not exist; that can't be checked until much later when 
    #  the first source map happens anyway
    ai=assignments_init[a]
    k=ai.keys()
    a_sid=ai['sid'] or None
    a_fid=None
    if 'fid' in k and ai['fid'] in tids:
        a_fid=ai['fid']
    a_bid=None
    if 'bid' in k and ai['bid'] in tids:
        a_bid=ai['bid']
    # remember a['tids'] is a list of lists: each list is a list of crop result ids,
    #   which is normally one line but could be several if the track wandered outside
    #   the crop boundary and back in again
    a_tids=[]
    for aitid_list in ai['tids']:
        atl=[x for x in aitid_list if x in tids]
        if atl:
            a_tids.append(atl) # to avoid appending an empty list
    # a_tids=[x for x in ai['tids'] if x in tids]
    a_cids=[x for x in ai['cids'] if x in tids]
    a_utids=[x for x in ai['utids'] if x in tids]
    if a_tids or a_cids or a_utids or a_fid or a_bid or a_sid:
        assignments[a]={
            'sid':a_sid,
            'bid':a_bid,
            'fid':a_fid,
            'tids':a_tids,
            'cids':a_cids,
            'utids':a_utids}

    # assignments[a]={}
    # assignments[a]['sid']=assignments_init[a]['sid'] # must assume the source assignment still exists
    # if assignments_init[a]['fid'] in tids:
    #     assignments[a]['fid']=assignments_init[a]['fid']
    # if assignments_init[a]['bid'] in tids:
    #     assignments[a]['bid']=assignments_init[a]['bid']
    # assignments[a]['tids']=[x for x in assignments_init[a]['tids'] if x in tids]
    # assignments[a]['cids']=[x for x in assignments_init[a]['cids'] if x in tids]
    # assignments[a]['utids']=[x for x in assignments_init[a]['utids'] if x in tids]
    # if assignments[a]['tids']==[] and assignments[a]['cids']==[] and assignments[a]['utids']==[] and 'bid' not in assignments[a].keys() and 'fid' not in assignments[a].keys()
# finally, prune any empty assignments; don't edit while iterating
assignmentsToDelete=[]
for at in assignments:
    a=assignments[at]
    if not a['bid'] and not a['fid'] and not a['tids'] and not a['cids'] and not a['utids']:
        assignmentsToDelete.append(at)
for atd in assignmentsToDelete:
    logging.info(' deleting empty assignment dict entry "'+atd+'"')
    del assignments[atd]
writeAssignmentsFile()
logging.info('assignments dict after pruning:'+json.dumps(assignments,indent=3))

# rotate track colors: red, green, blue, orange, cyan, purple, then darker versions of each
trackColorDict={
    'a':'#FF0000',
    'b':'#00CD00',
    'c':'#0000FF',
    'd':'#FFAA00',
    'e':'#009AFF',
    'f':'#A200FF',
    'g':'#C00000',
    'h':'#006900',
    'i':'#0000C0',
    'j':'#BC7D00',
    'k':'#0084DC',
    'l':'#8600D4'} # default specified in .get function

efids=sts2.mapData['ids']['Folder'] # existing (target map) folder IDs
logging.info('Existing folder ids:'+str(efids))
for fid in efids:
    f=sts2.getFeatures(id=fid)[0]
    logging.info('  Folder:'+str(f))
    t=f['properties']['title']
    if t:
        logging.info('Detected existing folder '+t+' with id '+fid)
        fids[t]=fid


def addCorrespondence(sid,tidOrList):
    if not isinstance(tidOrList,list):
        tidOrList=[tidOrList]
    for tid in tidOrList:
        corr.setdefault(sid,[]).append(tid)
    # write the correspondence file
    with open(corrFileName,'w') as corrFile:
        corrFile.write(json.dumps(corr,indent=3))

def createAssignmentEntry(t,sid):
    t=t.upper()
    if t in assignments.keys():
        logging.info('   assignment entry already exists')
    else:
        logging.info('creating assignment entry for assignment '+t)
        assignments[t]={
            'bid':None,
            'fid':None,
            'sid':sid,
            'cids':[],
            'tids':[],
            'utids':[]}
    # create the assignment folder if needed
    if t in fids.keys():
        logging.info('   assignment folder already exists')
        fid=fids[t]
    else:
        logging.info('   creating assignment folder '+t)
        fid=sts2.addFolder(t)
        fids[t]=fid
    assignments[t]['fid']=fid
    if sid: # this function could be called before sid is known, but eventually it would be called again when sid is known
        addCorrespondence(sid,fid)

def addAssignment(f):
    p=f['properties']
    t=p.get('title','').upper()
    id=f['id']

    createAssignmentEntry(t,id)
    fid=assignments[t]['fid']
    assignments[t]['sid']=id # assignment object id in source map
    # logging.info('fids.keys='+str(fids.keys()))
    g=f['geometry']
    gc=g['coordinates']
    gt=g['type']
    if gt=='Polygon':
        logging.info('drawing boundary polygon for assignment '+t)
        bid=sts2.addPolygon(gc[0],title=t,folderId=fid,strokeWidth=8,strokeOpacity=0.4,fillOpacity=0.0)
        assignments[t]['bid']=bid
        addCorrespondence(id,bid)
        logging.info('boundary created for assingment '+t+': '+assignments[t]['bid'])
        # since addPolygon adds the new object to .mapData immediately, no new 'since' request is needed
        if assignments[t]['utids']!=[]:
            cropUncroppedTracks()
        writeAssignmentsFile()
    elif gt=='LineString':
        logging.info('drawing boundary/line for assignment '+t)
        bid=sts2.addLine(gc,title=t,folderId=fid,strokeWidth=8,strokeOpacity=0.4)
        assignments[t]['bid']=bid
        addCorrespondence(id,bid)
        logging.info('boundary created for assingment '+t+': '+assignments[t]['bid'])
        # since addLine adds the new object to .mapData immediately, no new 'since' request is needed
        if assignments[t]['utids']!=[]:
            cropUncroppedTracks()
        writeAssignmentsFile()
    else:
        logging.error('newly detected assignment '+t+' has an unhandled geometry type '+gt)

def addShape(f):
    p=f['properties']
    g=f['geometry']
    gt=g['type']
    gc=g['coordinates']
    t=p['title']
    sid=f['id']
    if gt=='LineString':
        tparse=parseTrackName(t)
        # if len(tparse)<3 or tparse[2]=='': # it's not a track
        if not tparse:
            logging.info('newly detected line '+t+': name does not appear to indicate association with an assignment')
            logging.info('creating line \''+t+'\' in default folder')
            lineID=sts2.addLine(gc,title=t,
                    color=p['stroke'],
                    description=p['description'],
                    opacity=p['stroke-opacity'],
                    width=p['stroke-width'],
                    pattern=p['pattern'])
            addCorrespondence(sid,lineID)
        else: # it's a track; crop it now if needed, since newFeatureCallback is called once per object, not once per sync interval
            at=tparse[0]+' '+tparse[1] # 'AA 101' - should match a folder name
            logging.info('entire assignments dict:')
            logging.info(json.dumps(assignments,indent=3))
            a=assignments.get(at,None)
            if a==None: # assignment entry hasn't been created yet
                logging.info('processing line \''+t+'\' which appears to belong to assignment \''+at+'\' which has not been processed yet.  Creating the assignment dictionary and adding this track to the uncropped tracks list.')
                createAssignmentEntry(at,None)
                a=assignments[at]
            # add the line in the assignment folder, and crop to the assignment shape
            logging.info('creating line \''+t+'\' in folder \''+at+'\'')
            logging.info('  assignment fid='+a['fid'])
            bid=a['bid']
            # color=trackColorList[(len(a['tids'])+len(a['utids']))%len(trackColorList)]
            color=trackColorDict.get(tparse[2].lower(),'#444444')
            uncroppedTrack=sts2.addLine(gc,title=tparse[0].upper()+tparse[1]+tparse[2].lower(),color=color,folderId=a['fid'])
            logging.info(' generated uncropped track '+uncroppedTrack)
            if bid==None:
                logging.info('   assignment boundary has not been processed yet; saving the uncropped track in utids')
                assignments[at]['utids'].append(uncroppedTrack)
                addCorrespondence(sid,uncroppedTrack)
                # logging.info('  utids:'+str(assignments[at]['utids']))
            else:
                logging.info('  assignment bid='+bid)
                croppedTrackList=sts2.crop(uncroppedTrack,a['bid'],beyond=0.001) # about 100 meters
                assignments[at]['tids'].append(croppedTrackList)
                addCorrespondence(sid,croppedTrackList)
                # sts2.doSync(once=True)
                # sts2.crop(track,a['bid'],beyond=0.001) # about 100 meters
            writeAssignmentsFile()
    elif gt=='Polygon':
        logging.info('creating polygon \''+t+'\' in default folder')
        polygonID=sts2.addPolygon(gc[0],
            title=t,
            stroke=p['stroke'],
            strokeWidth=p['stroke-width'],
            strokeOpacity=p['stroke-opacity'],
            fillOpacity=p['fill-opacity'],
            description=p['description'])
        addCorrespondence(sid,polygonID)

def addMarker(f):
    p=f['properties']
    g=f['geometry']
    gt=g['type']
    if gt!='Point':
        logging.info('attempting to add a marker whose geometry type is '+gt+'; skipping')
        return(-1)
    t=p['title']
    gc=g['coordinates']
    logging.info('creating marker \''+t+'\' in default folder')
    markerID=sts2.addMarker(gc[1],gc[0],title=t,
                    color=p.get('marker-color',None),
                    rotation=p.get('marker-rotation',None),
                    size=p.get('marker-size',1),
                    description=p['description'],
                    symbol=p['marker-symbol'])
    logging.info('sts2.mapData after addMarker:'+json.dumps(sts2.mapData,indent=3))
    addCorrespondence(f['id'],markerID)

def addClue(f):
    p=f['properties']
    g=f['geometry']
    gt=g['type']
    if gt!='Point':
        logging.info('attempting to add a clue whose geometry type is '+gt+'; skipping')
        return(-1)
    t=p['title']
    gc=g['coordinates']
    logging.info('creating clue \''+t+'\' in default folder')
    clueID=sts2.addMarker(gc[1],gc[0],title=t,symbol='clue',description=p['description'])
    addCorrespondence(f['id'],clueID)

def cropUncroppedTracks():
    logging.info('inside cropUncroppedTracks:')
    for a in assignments:
        bid=assignments[a]['bid']
        if bid is not None:
            logging.info('  Assignment '+a+': cropping '+str(len(assignments[a]['utids']))+' uncropped tracks:'+str(assignments[a]['utids']))
            for utid in assignments[a]['utids']:
                # since newly created features are immediately added to the local cache,
                #  the boundary feature should be available by this time
                croppedTrackLines=sts2.crop(utid,bid,beyond=0.001) # about 100 meters
                logging.info('crop return value:'+str(croppedTrackLines))
                assignments[a]['tids'].append(croppedTrackLines)
                # cropped track line(s) should correspond to the source map line, 
                #  not the source map assignment; source map line id will be
                #  the corr key whose val is the utid; also remove the utid
                #  from that corr val list
                # logging.info('    corr items:'+str(corr.items()))
                slidList=[list(i)[0] for i in corr.items() if list(i)[1]==[utid]]
                if len(slidList)==1:
                    slid=slidList[0]
                    logging.info('    corresponding source line id:'+str(slid))
                    corr[slid]=[]
                    addCorrespondence(slid,croppedTrackLines)
                else:
                    logging.error('    corresponding source map line id could not be determined')
                    logging.error('    corresponding source line id list:'+str(slidList))
                # assignments[a]['utids'].remove(utid)
            assignments[a]['utids']=[] # don't modify the list during iteration over the list!
            writeAssignmentsFile()
        else:
            logging.info('  Assignment '+a+' has '+str(len(assignments[a]['utids']))+' uncropped tracks, but the boundary has not been imported yet; skipping.')

# criteria for a 'match': if a feature exists on the target map meeting these criteria,
#   then it corresponds to the newly read source map feature: don't create a new feature
#   on the target map; instead, make an entry in corr{} and update the target map feature
#   if needed; we should be pretty strict here, since any non-matching target map features
#   can be deleted, and the newly imported feature can be used instead
#  folder: target title is identical to source title
#  marker: 
def newFeatureCallback(f):
    p=f['properties']
    c=p['class']
    t=p.get('title','')
    sid=f['id']

    logging.info('newFeatureCallback: class='+c+'  title='+t+'  id='+sid)

    # source id might have a corresponding target id; if all corresponding target ids still exist, skip    
    tids=sum(sts2.mapData['ids'].values(),[])    
    if sid in corr.keys():
        logging.info(' source feautre exists in correspondence dictionary')
        if all(i in tids for i in corr[sid]):
            logging.info('  all corresponding features exist in the target map; skipping')
            # crop uncropped tracks even if the assignment already exists in the target;
            #  this will crop any tracks that were imported anew on restart
            if c=='Assignment':
                cropUncroppedTracks()
            return
        else:
            logging.info('  but target map does not contain all of the specified features; adding the feature to the target map')
    else:
        logging.info(' no correspondence entry found; adding the feature to the target map')

    if c=='Assignment':
        a=addAssignment(f)

    # new assignment:
    # 1. add a folder with name = assignment title (include the team# - we want one folder per pairing)
    # 2. add a shape (line or polygon) in that folder, with same geometry as the assignment
    # if c=='Assignment':
    #     t=t.upper()

    #     # create the assignment folder if needed
    #     if t in fids.keys():
    #         fid=fids[t]
    #     else:
    #         fid=sts2.addFolder(t)
    #         fids[t]=fid
        
    #     # logging.info('fids.keys='+str(fids.keys()))
    #     g=f['geometry']
    #     gc=g['coordinates']
    #     gt=g['type']
    #     if gt=='Polygon':
    #         existingAssignment=sts2.getFeatures(featureClass=c,title=t)[0]
    #         if existingAssignment:
    #             sts2.editObject(id=existingAssignment['id'],geometry=g)
    #         else:
    #             sts2.addPolygon(gc[0],title=t,folderId=fid)
    #     elif gt=='LineString':
    #         sts2.addLine(gc,title=t,folderId=fid)
    #     else:
    #         logging.error('newly detected assignment '+t+' has an unhandled geometry type '+gt)
    #         return False

#     # new shape:
#     # 1. if line:
#     #   a. if title indicates it's a track:
#     #     i. create a new line with same geometry in the assignment folder
#     #     - creaete the assignment folder if it doesn't already exist; the assignment object
#     #        may not have been processed yet
#     #   b. otherwise:
#     #     i. create a new line with same geometry in the default folder
#     # 2. if polygon:
#     #   a. create a new polygon with the same geometry in the default folder

    if c=='Shape':
        addShape(f)
        # g=f['geometry']
        # gc=g['coordinates']
        # gt=g['type']
# #         # if gt=='Polygon':
# #         #     sts2.addPolygon(gc[0],title=t,folderId=fid)
        # if gt=='LineString':
        #     tparse=re.split('(\d+)',t.upper().replace(' ',''))
        #     if len(tparse)==3 and tparse[2]=='':
        #         logging.info()
#                 logging.error('new line '+t+' detected, but name does not appear to indicate a track')
#                 return False
#             at=tparse[0]+' '+tparse[1] # 'AA 101' - should match a folder name
#             # logging.info('at='+at)
#             # logging.info('fids.keys='+str(fids.keys()))
#             a=assignments[at]
            
#             # create the assignment folder if needed
#             if at in fids.keys():
#                 fid=fids[at]
#             else:
#                 fid=sts2.addFolder(t)
#                 fids[t]=fid

#             # add the line in the assignment folder, and crop to the assignment shape
#             color=trackColorList[len(a['utids'])+len(a['tids'])]
#             track=sts2.addLine(gc,title=tparse[0].upper()+tparse[1]+tparse[2].lower(),color=color,folderId=fid)
#             sts2.doSync(once=True) # since crop needs updated .mapData
#             sts2.crop(track,at,beyond=0.001) # about 100 meters
#             a['tids'].append(track)
#             logging.info(' generated track '+track)

#         else:
#             logging.error('new object '+t+' has an unhandled geometry type '+gt)
#             return False

        # new marker:
        #  add the new marker in the default markers folder

    if c=='Marker':
        addMarker(f)

    if c=='Clue':
        addClue(f)
    
        # new clue:
        #  add a new marker in the assignment folder, using the clue symbol

        # for folder in sts2.getFeatures('Folder',timeout=10):
        #     if folder['properties']['title']==t:
        #         sts2.addLine(f['geometry']['coordinates'],title=t,folderId=folder['id'],timeout=10)
        #         # sts2.editObject(id=id,properties={'folderId':folder['id']})


def propertyUpdateCallback(f):
    sid=f['id']
    sp=f['properties']
    logging.info('propertyUpdateCallback called for '+sp['class']+':'+sp['title'])
    # 1. determine which target-map feature, if any, corresponds to the edited source-map feature
    if sid in corr.keys():
        cval=corr[sid]
        logging.info('  cval:'+str(cval))
        if len(cval)==1: # exactly one correlating feature exists
            logging.info('  exactly one target map feature corresponds to the source map feature; updating the target map feature properties')
            tf=sts2.getFeature(id=cval[0])
            tp=tf['properties']
            # map properties from source to target, based on source class; start with the existing target
            #  map feature properties, and only copy the appropriate properties from the source feature
            c=sp['class']
            if c=='Clue':
                logging.info('  mapping properties from Clue to Marker')
                tp['title']=sp['title']
                tp['description']=sp['description']
            elif c=='Assignment':
                tp['title']=sp['title']
            else:
                tp=sp # for other feature types, copy all properties from source
            sts2.editObject(id=cval[0],properties=tp)
        elif len(cval)==2 and sp['class']=='Assignment': # assignment with folder and boundary already created
            # change the title of all corresponding objects (usually just folder and boundary)
            #  and also move the assignments dict entry to the new name
            logging.info('changing assignment name.  existing assigments dict:')
            logging.info(json.dumps(assignments,indent=3))
            oldTitle=None
            for tid in cval:
                tf=sts2.getFeature(id=tid)
                tp=tf['properties']
                oldTitle=tp['title']
                tp['title']=sp['title'].upper()
                sts2.editObject(id=tid,properties=tp)
            if oldTitle:
                assignments[tp['title']]=assignments[oldTitle]
                del assignments[oldTitle]
            logging.info('new assigments dict:')
            logging.info(json.dumps(assignments,indent=3))
            writeAssignmentsFile()
        else:
            logging.info('  more than one existing target map feature corresponds to the source map feature; nothing edited due to ambuguity')
    else:
        logging.info('  source map object does not have any corresponding feature in target map; nothing edited')

# parseTrackName: return False if not a track, or [assignment,team,suffix] if a track
def parseTrackName(t):
    tparse=re.split('(\d+)',t.upper().replace(' ',''))
    if len(tparse)==3:
        return tparse
    else:
        return False

def geometryUpdateCallback(f):
    sid=f['id']
    sp=f['properties']
    sg=f['geometry']
    # if the edited source object is a track (a linestring with appropriate name format),
    #  delete all corresponding target map features (the crop operation could have resulted in
    #  multiple lines) then re-import the feature from scratch, which will also re-crop it;
    # otherwise, edit the geometry of all corresponding features that have a geometry entry
    #  (i.e. when an assigment boundary is edited, the assignment folder has no geometry)
    logging.info('geometryUpdateCallback called for '+sp['class']+':'+sp['title'])
    if sid in corr.keys():
        tparse=parseTrackName(sp['title'])
        if sg['type']=='LineString' and sp['class']=='Shape' and tparse:
            logging.info('  edited object '+sp['title']+' appears to be a track; correspoding previous imported and cropped tracks will be deleted, and the new track will be re-imported (and re-cropped)')
            corrList=corr[sid]
            for ttid in corr[sid]:
                sts2.delObject('Shape',ttid)
            # also delete from the assignments dict and correspondence dict, so that it will be added anew
            at=tparse[0]+' '+tparse[1]
            # don't modify list while iterating!
            newTidList=[]
            for tidList in assignments[at]['tids']:
                if not all(elem in tidList for elem in corrList):
                    newTidList.append(tidList)
            assignments[at]['tids']=newTidList
            del corr[sid]
            newFeatureCallback(f) # this will crop the track automatically
        else:
            for tid in corr[sid]:
                if 'geometry' in sts2.getFeature(id=tid).keys():
                    logging.info('  corresponding target map feature '+tid+' has geometry; setting it equal to the edited source feature geometry')
                    sts2.editObject(id=tid,geometry=sg)
                else:
                    logging.info('  corresponding target map feature '+tid+' has no geometry; no edit performed')

    # # 1. determine which target-map feature, if any, corresponds to the edited source-map feature
    # if sid in corr.keys():
    #     cval=corr[sid]
    #     logging.info('cval:'+str(cval))
    #     if len(cval)==1: # exactly one corresponding feature exists
    #         logging.info('exactly one target map feature corresponds to the source map feature; updating the target map feature geometry')
    #         sts2.editObject(id=cval[0],geometry=sg)
    #         # if it was a track, delete all corresponding target map features, then re-import (which will re-crop it)
    #         if sg['type']=='LineString':
    #             for a in assignments:
    #                 logging.info('  checking assignment: tids='+str(assignments[a]['tids']))
    #                 if cval[0] in assignments[a]['tids']:
    #                     logging.info('  the updated geometry is a track belonging to '+assignments[a]['title']+': will re-crop using the new geometry')
    #                     sts2.crop(cval[0],assignments[a]['bid'],beyond=0.001)
    #     else:
    #         logging.info('more than one existing target map feature corresponds to the source map feature; nothing edited due to ambuguity')
    else:
        logging.info('source map object does not have any corresponding feature in target map; nothing edited')

def deletedFeatureCallback(sid):
    logging.info('deletedFeatureCallback called')
    # 1. determine which target-map feature, if any, corresponds to the edited source-map feature
    if sid in corr.keys():
        cval=corr[sid]
        for tid in cval:
            logging.info('deleting corresponding target map feature '+tid)
            sts2.delObject(f['properties']['class'],existingId=tid)
    else:
        logging.info('source map object does not have any corresponding feature in target map; nothing deleted')

try:
    sts1=SartopoSession('localhost:8080',sourceMapID,
        newFeatureCallback=newFeatureCallback,
        propertyUpdateCallback=propertyUpdateCallback,
        geometryUpdateCallback=geometryUpdateCallback,
        deletedFeatureCallback=deletedFeatureCallback,
        syncDumpFile='../../'+sourceMapID+'.txt',
        syncTimeout=10)
except:
    sys.exit()

# initial sync is different than callback handling because:
#    ...
#
# on the initial sync, pay attention to the sequence:
# 1. read assignments from source map: create folders and boundary shapes in target map
# 2. read shapes from source map: for completed search tracks (based on name),
#      draw the line in the target map assignment folder
# 3. perform a fresh since request on target map, so that newly
#      drawn lines will appear in .mapData as needed by crop()
# 4. in target map, color the tracks in alphabetical order
# 5. in target map, crop tracks to assigment boundaries

# # 1. read assignments
# for f in sts1.getFeatures(featureClass='Assignment'):
#     addAssignment(f)
    
# # 2. read shapes
# for f in sts1.getFeatures('Shape'):
#     addShape(f)

# for f in sts1.getFeatures('Marker'):
#     addMarker(f)

# for f in sts1.getFeatures('Clue'):
#     addClue(f)

# # 3. do a new since request in the target map
# sts2.doSync(once=True)

# 4. color the tracks in alphabetical order



# initial processing complete; now register the callback
# sts1.newFeatureCallback=newFeatureCallback

# need to run this program in a loop - it's not a background/daemon process
while True:
   time.sleep(5)
