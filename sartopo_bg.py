from sartopo_python import SartopoSession
import logging
import re

# open a session on the target map first, since nocb definition checks for it
sts2=SartopoSession('localhost:8080','0SD',sync=False,syncTimeout=10)

fids={} # maintain a dictionary of folder names and ids

def nocb(f):
    p=f['properties']
    c=p['class']
    t=p.get('title','')
    id=f['id']


    # new assignment:
    # 1. add a folder with name = assignment title (include the team# - we want one folder per pairing)
    # 2. add a shape (line or polygon) in that folder, with same geometry as the assignment
    if c=='Assignment':
        t=t.upper()
        fid=sts2.addFolder(t)
        fids[t]=fid
        g=f['geometry']
        gc=g['coordinates']
        gt=g['type']
        if gt=='Polygon':
            sts2.addPolygon(gc[0],title=t,folderId=fid)
        elif gt=='LineString':
            sts2.addLine(gc,title=t,folderId=fid)
        else:
            logging.error('newly detected assignment '+t+' has an unhandled geometry type '+gt)
            return False
        

    # new shape:
    # 1. if line:
    #   a. if title indicates it's a track:
    #     i. create a new line with same geometry in the appropriate assignment folder
    #   b. otherwise:
    #     i. create a new line with same geometry in the default folder
    # 2. if polygon:
    #   a. create a new polygon with the same geometry in the default folder

    elif c=='Shape':
        g=f['geometry']
        gc=g['coordinates']
        gt=g['type']
        # if gt=='Polygon':
        #     sts2.addPolygon(gc[0],title=t,folderId=fid)
        if gt=='LineString':
            tparse=re.split('(\d+)',t.upper().replace(' ',''))
            if len(tparse)<3:
                logging.error('new line '+t+' detected, but name does not appear to indicate a track')
                return False
            at=tparse[0]+' '+tparse[1] # 'AA 101' - should match a folder name
            logging.info('at='+at)
            logging.info('fids.keys='+str(fids.keys()))
            if at in fids.keys():
                fid=fids[at]
                track=sts2.addLine(gc,title=t,folderId=fid)
                sts2.crop(track,at,beyond=0.001) # about 100 meters
            else:
                logging.error('new line '+t+' detected, which appears to belong to assignment '+at+' which does not currently exist in this map.')
                return False
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
    newObjectCallback=nocb,
    syncTimeout=10)

# need to run this program in a loop - it's not a background/daemon process
while True:
    pass





