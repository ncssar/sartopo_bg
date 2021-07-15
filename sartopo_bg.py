from sartopo_python import SartopoSession
import logging
import re
import time

# do not register the callbacks until after the initial processing; that way we
#  can be sure to process assignments first

# assignments - dictionary of assignment data, created when first associated object is processed
# NOTE - we really want to be able to recreate all of this at runtime, instead of relying on
#   a file somewhere
#  key = assignment title (name and number; i.e. we want one dict entry per pairing/'outing')
#  val = dictionary
#     bid - id of boundary object (in the target map)
#     fid - id of folder object (in the target map)
#     cids - list of ids of associated clues (in the target map)
#     tids - list of ids of associated tracks (in the target map)
#     utids - list of uncropped track ids (since the track may be processed before the boundary)

# open a session on the target map first, since nocb definition checks for it
sts2=SartopoSession('localhost:8080','0SD',sync=False,syncTimeout=10,syncDumpFile='../../0SD.txt')

assignments={}
fids={}

# rotate track colors: red, green, blue, orange, cyan, purple, then darker versions of each
trackColorList=['#FF0000','#00FF00','#0000FF','#FFAA00','#009AFF','#A200FF',
        '#C00000','#009B00','#0000C0','#BC7D00','#0084DC','#8600D4']

for fid in sts2.mapData['ids']['Folder']:
    t=sts2.getFeatures(id=fid)['properties']['title'][0]
    if t:
        logging.info('Detected existing folder '+t+' with id '+id)
        fids[t]=fid


def nocb(f):
    p=f['properties']
    c=p['class']
    t=p.get('title','')
    id=f['id']

#     # new assignment:
#     # 1. add a folder with name = assignment title (include the team# - we want one folder per pairing)
#     # 2. add a shape (line or polygon) in that folder, with same geometry as the assignment
#     if c=='Assignment':
#         t=t.upper()

#         # create the assignment folder if needed
#         if t in fids.keys():
#             fid=fids[t]
#         else:
#             fid=sts2.addFolder(t)
#             fids[t]=fid
        
#         # logging.info('fids.keys='+str(fids.keys()))
#         g=f['geometry']
#         gc=g['coordinates']
#         gt=g['type']
#         if gt=='Polygon':
#             existingAssignment=sts2.getFeatures(featureClass=c,title=t)[0]
#             if existingAssignment:
#                 sts2.editObject(id=existingAssignment['id'],geometry=g)
#             else:
#                 sts2.addPolygon(gc[0],title=t,folderId=fid)
#         elif gt=='LineString':
#             sts2.addLine(gc,title=t,folderId=fid)
#         else:
#             logging.error('newly detected assignment '+t+' has an unhandled geometry type '+gt)
#             return False

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
        g=f['geometry']
        gc=g['coordinates']
        gt=g['type']
#         # if gt=='Polygon':
#         #     sts2.addPolygon(gc[0],title=t,folderId=fid)
        if gt=='LineString':
            tparse=re.split('(\d+)',t.upper().replace(' ',''))
            if len(tparse)<3 or tparse[2]=='':
                logging.error('new line '+t+' detected, but name does not appear to indicate a track')
                return False
            at=tparse[0]+' '+tparse[1] # 'AA 101' - should match a folder name
            # logging.info('at='+at)
            # logging.info('fids.keys='+str(fids.keys()))
            a=assignments[at]
            
            # create the assignment folder if needed
            if at in fids.keys():
                fid=fids[at]
            else:
                fid=sts2.addFolder(t)
                fids[t]=fid

            # add the line in the assignment folder, and crop to the assignment shape
            color=trackColorList[len(a['utids'])+len(a['tids'])]
            track=sts2.addLine(gc,title=tparse[0].upper()+tparse[1]+tparse[2].lower(),color=color,folderId=fid)
            sts2.doSync(once=True) # since crop needs updated .mapData
            sts2.crop(track,at,beyond=0.001) # about 100 meters
            a['tids'].append(track)
            logging.info(' generated track '+track)

        else:
            logging.error('new object '+t+' has an unhandled geometry type '+gt)
            return False

        # new marker:
        #  add the new marker in the default markers folder

        # new clue:
        #  add a new marker in the assignment folder, using the clue symbol

        # for folder in sts2.getFeatures('Folder',timeout=10):
        #     if folder['properties']['title']==t:
        #         sts2.addLine(f['geometry']['coordinates'],title=t,folderId=folder['id'],timeout=10)
        #         # sts2.editObject(id=id,properties={'folderId':folder['id']})


sts1=SartopoSession('localhost:8080','V80',
    # newObjectCallback=nocb,
    syncTimeout=10)

# on the initial sync, pay attention to the sequence:
# 1. read assignments from source map: create folders and boundary shapes in target map
# 2. read shapes from source map: for completed search tracks (based on name),
#      draw the line in the target map assignment folder
# 3. perform a fresh since request on target map, so that newly
#      drawn lines will appear in .mapData as needed by crop()
# 4. in target map, color the tracks in alphabetical order
# 5. in target map, crop tracks to assigment boundaries

# 1. read assignments
for f in sts1.getFeatures(featureClass='Assignment'):
    p=f['properties']
    t=p.get('title','').upper()
    id=f['id']

    assignments[t]={
        'bid':None,
        'fid':None,
        'cids':[],
        'tids':[],
        'utids':[]}

    # create the assignment folder if needed
    if t in fids.keys():
        fid=fids[t]
    else:
        fid=sts2.addFolder(t)
        fids[t]=fid
    assignments[t]['fid']=fid
    
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
        assignments[t]['bid']=sts2.addPolygon(gc[0],title=t,folderId=fid,strokeOpacity=0.4,fillOpacity=0.0)
    elif gt=='LineString':
        assignments[t]['bid']=sts2.addLine(gc,title=t,folderId=fid)
    else:
        logging.error('newly detected assignment '+t+' has an unhandled geometry type '+gt)

# 2. read shapes
for f in sts1.getFeatures('Shape'):
    p=f['properties']
    g=f['geometry']
    gt=g['type']
    if gt=='LineString':
        t=p['title']
        tparse=re.split('(\d+)',t.upper().replace(' ',''))
        if len(tparse)<3 or tparse[2]=='':
            logging.info('newly detected line '+t+': name does not appear to indicate association with an assignment')
            continue
        at=tparse[0]+' '+tparse[1] # 'AA 101' - should match a folder name
        a=assignments[at]

        # add the line in the assignment folder, and crop to the assignment shape
        logging.info('creating line \''+t+'\' in folder \''+at+'\'')
        logging.info('  assignment fid='+a['fid'])
        logging.info('  assignment bid='+a['bid'])
        gc=g['coordinates']
        color=trackColorList[len(a['utids'])]
        track=sts2.addLine(gc,title=tparse[0].upper()+tparse[1]+tparse[2].lower(),color=color,folderId=a['fid'])
        assignments[at]['utids'].append(track)
        logging.info(' generated track '+track)
        logging.info('  utids:'+str(assignments[at]['utids']))
        # sts2.doSync(once=True)
        # sts2.crop(track,a['bid'],beyond=0.001) # about 100 meters

# 3. do a new since request in the target map
sts2.doSync(once=True)

# 4. color the tracks in alphabetical order

# 5. crop tracks
for a in assignments:
    # print('Cropping '+str(len(assignments[a]['utids']))+' lines:'+str(assignments[a]['utids']))
    for utid in assignments[a]['utids']:
        r=sts2.crop(utid,assignments[a]['bid'],beyond=0.001) # about 100 meters
        # logging.info('crop return value:'+str(r))
        assignments[a]['tids']+=r
    assignments[a]['utids']=[] # don't modify the list during iteration over the list!

# initial processing complete; now register the callback
sts1.newObjectCallback=nocb

# need to run this program in a loop - it's not a background/daemon process
while True:
    time.sleep(5)





