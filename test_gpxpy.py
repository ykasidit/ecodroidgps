import gpxpy
import gpxpy.gpx
import datetime


def test():
    gpx = gpxpy.gpx.GPX()
    gpx.creator = "Data logged by EcoDroidGPS Bluetooth GPS -- http://www.ClearEvo.com -- GPX engine by gpx.py -- https://github.com/tkrajina/gpxpy"

    # Create first track in our GPX:
    gpx_track = gpxpy.gpx.GPXTrack()
    gpx.tracks.append(gpx_track)
    
    # Create first segment in our GPX track:
    gpx_segment = gpxpy.gpx.GPXTrackSegment()
    gpx_track.segments.append(gpx_segment)

    # Create points:
    dt = datetime.datetime.now()
    gpx_segment.points.append(gpxpy.gpx.GPXTrackPoint(2.1234, 5.1234, elevation=1234, time=dt))
    gpx_segment.points.append(gpxpy.gpx.GPXTrackPoint(2.1235, 5.1235, elevation=1235, time=dt))
    gpx_segment.points.append(gpxpy.gpx.GPXTrackPoint(2.1236, 5.1236, elevation=1236, time=dt))

    assert len(gpx_segment.points) == 3

    # You can add routes and waypoints, too...

    fn = "gpx_out_test.xml"
    with open(fn, "wb") as f:
        buff = gpx.to_xml()
        f.write(buff)
        print('Created GPX file {} buff:\n {}'.format(fn, buff))
        

    del gpx_segment.points[:]
    assert len(gpx_segment.points) == 0

    fn = "gpx_out_test_after_clear.xml"
    with open(fn, "wb") as f:
        buff = gpx.to_xml()
        f.write(buff)
        print('Created GPX file {} buff:\n {}'.format(fn, buff))


if __name__ == "__main__":
    test()
