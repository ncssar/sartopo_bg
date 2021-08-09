from sartopo_python import SartopoSession
import logging
import re
import time
import sys

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

# open a session on the target map first, since nocb definition checks for it
sts2=SartopoSession('localhost:8080','0SD',sync=False,syncTimeout=10,syncDumpFile='../../0SD.txt')

assignments={}
fids={} # folder IDs
corr={} # correspondence dictionary: key=source-map-ID, val=list-of-target-map-IDs

# rotate track colors: red, green, blue, orange, cyan, purple, then darker versions of each
trackColorList=['#FF0000','#00FF00','#0000FF','#FFAA00','#009AFF','#A200FF',
        '#C00000','#009B00','#0000C0','#BC7D00','#0084DC','#8600D4']

efids=sts2.mapData['ids']['Folder'] # existing (target map) folder IDs
logging.info('Existing folder ids:'+str(efids))
for fid in efids:
    f=sts2.getFeatures(id=fid)[0]
    logging.info('  Folder:'+str(f))
    t=f['properties']['title']
    if t:
        logging.info('Detected existing folder '+t+' with id '+fid)
        fids[t]=fid

def createAssignmentEntry(t):
    if t in assignments.keys():
        logging.info('   assignment entry already exists')
    else:
        logging.info('creating assignment entry for assignment '+t)
        assignments[t]={
            'bid':None,
            'fid':None,
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

def addAssignment(f):
    p=f['properties']
    t=p.get('title','').upper()
    id=f['id']

    createAssignmentEntry(t)
    fid=assignments[t]['fid']
    assignments[t]['sid']=id # assignment object id in source map
    # logging.info('fids.keys='+str(fids.keys()))
    g=f['geometry']
    gc=g['coordinates']
    gt=g['type']
    if gt=='Polygon':
        # existingBoundary=sts2.getFeatures(featureClass='Shape',title=t)[0]
        # if existingBoundary:
        #     ebid=existingBoundary['id']
        #     assignments[t]['bid']=ebid
        #     sts2.editObject(id=ebid,geometry=g)
        # else:
        logging.info('drawing boundary polygon for assignment '+t)
        assignments[t]['bid']=sts2.addPolygon(gc[0],title=t,folderId=fid,strokeWidth=8,strokeOpacity=0.4,fillOpacity=0.0)
        logging.info('boundary created for assingment '+t+': '+assignments[t]['bid'])
        # an immediate call to cropUncroppedTracks means the new boundary will probably not exist in the cache yet;
        #  should we recode addPolygon to add the returned json to the cache directly?  It is an actual response from 
        #  the server so it should be safe to do so.  But - much cleaner to let the since response take care of it.
        if assignments[t]['utids']!=[]:
            # sts2.refresh(forceImmediate=True)
            cropUncroppedTracks()
    elif gt=='LineString':
        assignments[t]['bid']=sts2.addLine(gc,title=t,folderId=fid,strokeWidth=8,strokeOpacity=0.4)
        if assignments[t]['utids']!=[]:
            # sts2.refresh(forceImmediate=True)
            cropUncroppedTracks()
    else:
        logging.error('newly detected assignment '+t+' has an unhandled geometry type '+gt)

def addShape(f):
    p=f['properties']
    g=f['geometry']
    gt=g['type']
    if gt=='LineString':
        t=p['title']
        tparse=re.split('(\d+)',t.upper().replace(' ',''))
        gc=g['coordinates']
        if len(tparse)<3 or tparse[2]=='': # it's not a track
            logging.info('newly detected line '+t+': name does not appear to indicate association with an assignment')
            logging.info('creating line \''+t+'\' in default folder')
            lineID=sts2.addLine(gc,title=t,
                    color=p['stroke'],
                    description=p['description'],
                    opacity=p['stroke-opacity'],
                    width=p['stroke-width'],
                    pattern=p['pattern'])
            corr[f['id']]=[lineID]
        else: # it's a track; crop it now if needed, since newObjectCallback is called once per object, not once per sync interval
            at=tparse[0]+' '+tparse[1] # 'AA 101' - should match a folder name
            a=assignments.get(at,None)
            if a==None: # assignment entry hasn't been created yet
                logging.info('processing line \''+t+'\' which appears to belong to assignment \''+at+'\' which has not been processed yet.  Creating the assignment dictionary and adding this track to the uncropped tracks list.')
                createAssignmentEntry(at)
                a=assignments[at]
            # add the line in the assignment folder, and crop to the assignment shape
            logging.info('assignments dictionatory:'+str(a))
            logging.info('creating line \''+t+'\' in folder \''+at+'\'')
            logging.info('  assignment fid='+a['fid'])
            bid=a['bid']
            color=trackColorList[(len(a['tids'])+len(a['utids']))%len(trackColorList)]
            uncroppedTrack=sts2.addLine(gc,title=tparse[0].upper()+tparse[1]+tparse[2].lower(),color=color,folderId=a['fid'])
            logging.info(' generated uncropped track '+uncroppedTrack)
            if bid==None:
                logging.info('   assignment boundary has not been processed yet; saving the uncropped track in utids')
                assignments[at]['utids'].append(uncroppedTrack)
                # logging.info('  utids:'+str(assignments[at]['utids']))
            else:
                logging.info('  assignment bid='+bid)
                croppedTrack=sts2.crop(uncroppedTrack,a['bid'],beyond=0.001) # about 100 meters
                assignments[at]['tids'].append(croppedTrack)
                # sts2.doSync(once=True)
                # sts2.crop(track,a['bid'],beyond=0.001) # about 100 meters

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
    corr[f['id']]=[markerID]

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
    corr[f['id']]=[clueID]

def cropUncroppedTracks():
    logging.info('inside cropUncroppedTracks:')
    for a in assignments:
        bid=assignments[a]['bid']
        if bid is not None:
            logging.info('  Assignment '+a+': cropping '+str(len(assignments[a]['utids']))+' uncropped lines:'+str(assignments[a]['utids']))
            for utid in assignments[a]['utids']:
                # since newly created features are immediately added to the local cache,
                #  the boundary feature should be available by this time
                r=sts2.crop(utid,bid,beyond=0.001) # about 100 meters
                # logging.info('crop return value:'+str(r))
                assignments[a]['tids'].append(r)
                # assignments[a]['utids'].remove(utid)
            assignments[a]['utids']=[] # don't modify the list during iteration over the list!
        else:
            logging.info('  Assignment '+a+' has '+str(len(assignments[a]['utids']))+' uncropped lines, but the boundary has not been imported yet; skipping.')

# criteria for a 'match': if a feature exists on the target map meeting these criteria,
#   then it corresponds to the newly read source map feature: don't create a new feature
#   on the target map; instead, make an entry in corr{} and update the target map feature
#   if needed; we should be pretty strict here, since any non-matching target map features
#   can be deleted, and the newly imported feature can be used instead
#  folder: target title is identical to source title
#  marker: 
def newObjectCallback(f):
    p=f['properties']
    c=p['class']
    t=p.get('title','')
    id=f['id']

    logging.info('newObjectCallback: class='+c+'  title='+t)

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
#         g=f['geometry']
#         gc=g['coordinates']
#         gt=g['type']
# #         # if gt=='Polygon':
# #         #     sts2.addPolygon(gc[0],title=t,folderId=fid)
#         if gt=='LineString':
#             tparse=re.split('(\d+)',t.upper().replace(' ',''))
#             if len(tparse)<3 or tparse[2]=='':
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


def propertyUpdateCallback(sid,sp):
    logging.info('propertyUpdateCallback called')
    # 1. determine which target-map feature, if any, corresponds to the edited source-map feature
    if sid in corr.keys():
        cval=corr[sid]
        logging.info('  cval:'+str(cval))
        if len(cval)==1: # exactly one correlating feature exists
            logging.info('  exactly one target map feature curresponds to the source map feature; updating the target map feature properties')
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
        else:
            logging.info('  more than one existing target map feature corresponds to the source map feature; nothing edited due to ambuguity')
    else:
        logging.info('  source map object does not have any corresponding feature in target map; nothing edited')

def geometryUpdateCallback(sid,sg):
    logging.info('geometryUpdateCallback called')
    # 1. determine which target-map feature, if any, corresponds to the edited source-map feature
    if sid in corr.keys():
        cval=corr[sid]
        logging.info('cval:'+str(cval))
        if len(cval)==1: # exactly one correlating feature exists
            logging.info('exactly one target map feature curresponds to the source map feature; updating the target map feature geometry')
            sts2.editObject(id=cval[0],geometry=sg)
        else:
            logging.info('more than one existing target map feature corresponds to the source map feature; nothing edited due to ambuguity')
    else:
        logging.info('source map object does not have any corresponding feature in target map; nothing edited')

def deletedObjectCallback(sid):
    logging.info('deletedObjectCallback called')
    # 1. determine which target-map feature, if any, corresponds to the edited source-map feature
    if sid in corr.keys():
        cval=corr[sid]
        for tid in cval:
            logging.info('deleting corresponding target map feature '+tid)
            sts2.delObject(f['properties']['class'],existingId=tid)
    else:
        logging.info('source map object does not have any corresponding feature in target map; nothing deleted')

sts1=SartopoSession('localhost:8080','V80',
    newObjectCallback=newObjectCallback,
    propertyUpdateCallback=propertyUpdateCallback,
    geometryUpdateCallback=geometryUpdateCallback,
    deletedObjectCallback=deletedObjectCallback,
    syncDumpFile='../../V80.txt',
    syncTimeout=10)

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
# sts1.newObjectCallback=newObjectCallback

# need to run this program in a loop - it's not a background/daemon process
while True:
   time.sleep(5)
