# sartopo_bg
sartopo background automation using sartopo_python

There are a lot of possible background sartopo tasks.  For now, this repo exclusively deals with Derief Map Generation.  The repo name may be changed accordingly.

# Debrief Map Generator

This tool generates high quality individual team debrief maps, with minimal need for user intervention.

In our experience, only these features should be included on the print map:

1. team assignment boundary
2. relevant portions of tracks of all team members
    - for roaming teams, such as trailing dogs or trackers, crop the tracks to some reasoably large distance (10km or so) from their starting assignment shape
    - for all other teams, crop the tracks to a bit beyond their assignment boundary
3. clues located by the team
4. clues located by other teams
5. other relevant map markers and lines that are not specific to the assignment (IC / CP, gates, trails, etc.)

The print map should be zoomed and positioned such that the page is mostly filled up by features from the first three of these categories, with a reasonable buffer.

Features in the last two categories should be drawn only if they are inside the print area determined by the first three categories.

Different SAR teams may find that different styles of debrief maps work better for their purposes.  Please send your feedback and ideas!

Generating good quality team debrief maps has always been elusive and labor intensive, to the point where it usually just doesn't happen, or, a cluttered or incomplete compromise map is used instead.  This compromises the quality of the team debrief process, while creating a lot of delay, and a lot of heartburn in the command post.  Hopefully, this tool can alleviate or even eliminate those problems.

Normally, with this tool running in the background for the duration of the incident, the only necessary user intervention is to click the 'generate PDF' button after all the tracks and clues for an assignment have been imported.

image::doc/dmg01.png

Sample incident map

image::doc/dmg02.png

Automatically generated debrief map - you might never need to view this map

image::doc/dmg03.png

Generated debrief map

image::doc/dmg04.png

Generated debrief map

image::doc/dmg05.png

Debrief Map Generator user interface

## Other ways to build debrief maps

For now, SARTopo still supports the concept of ownership.  This concept will be eliminated at some point in the future.
- Operational Periods own Assignments
- Assignments own Tracks, Clues, and Waypoints
  - A Track is a Line that is owned by an Assignment
  - a Clue is a Marker that is owned by an Assignment
  - a Waypoint is a Marker that is owned by an Assignment but which has no clue-relevant data

Printing an 'Assignment Map' from Assignment Bulk Ops will generate a PDF that includes the assignment boundary and everything owned by it.  

So, if data imported from searcher GPSes is converted to 'Tracks' and 'Clues' as appropriate, or is imported 'to the assignment' such that they are Tracks and Clues from the start, then printing an Assignment Map, can get close to the goal - but their are significant hurdles and drawbacks:
- making sure that all imported lines and markers are Tracks and Clues owned by the proper assigment can be very labor-intensive and error-prone
- 'cleaning up' the Tracks, by cutting and deleting, is labor-intensive and error-prone; but, since the bulk-ops-generated Assignment Map extents are determined by the largest extents of owned features, skipping the cleanup step means that the benefits of Assignment Map automatic zooming and positioning are lost.  If a searcher's tracks include a straight line from home, that will be part of the generated Assignment Map unless cleanup is done first
- the assignment boundary will be drawn with a fixed amount of opacity, obscuring the map baselayer beneath it, and generally making annotations during debrief less clear
- features that are not owned by the assignment, such as IC / CP, gates, trails, etc, are not shown on the generated Assignment Map

A common alternative to printing Assignment Maps from Bulk Ops is to just print an area of the incident map, maybe spending a few seconds first to uncheck some categories of features that should not be shown on the printed map.  In some cases, this gets fairly close to the goal, but care is still needed in map preparation.

