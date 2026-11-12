"""One predeclared Mission -> RAPTOR case. Pure geometry; no simulator imports."""
import math

SEED = 20261109
MISSION_NED = [(3., 0., -3.), (3., 3., -3.4), (-2., 3., -3.), (-2., -2., -3.), (0., 0., -3.)]
GAP = (7., 7.32)
DURATION = 18.


def hermite(p0, v0, p1, v1, duration, t):
    """Quintic, zero acceleration at both ends. Return position/velocity/accel."""
    u = min(1., max(0., t / duration))
    d = p1 - p0 - v0 * duration
    dv = (v1 - v0) * duration
    c = [p0, v0 * duration, 0., 10*d - 4*dv, -15*d + 7*dv, 6*d - 3*dv]
    return (sum(c[k]*u**k for k in range(6)),
            sum(k*c[k]*u**(k-1) for k in range(1, 6))/duration,
            sum(k*(k-1)*c[k]*u**(k-2) for k in range(2, 6))/duration**2)


def trajectory(t, origin, velocity, yaw):
    # Brake with C2 continuity, then a small 3D loop with nonzero through velocities.
    v = list(velocity)
    knots = [(0., [0., 0., 0.], v),
             (2., [.8*v[0], .8*v[1], .4*v[2]], [0., 0., 0.]),
             (5., [-1., 1., -.3], [-.4, 0., 0.]),
             (8., [-2., 0., 0.], [0., -.3, .1]),
             (11., [-1., -1., .3], [.4, 0., 0.]),
             (14., [0., 0., 0.], [0., 0., 0.])]
    t = max(0., t)
    if t >= 14.:
        p, speed, acc = list(origin), [0.]*3, [0.]*3
    else:
        k = next(i for i in range(len(knots)-1) if knots[i][0] <= t < knots[i+1][0])
        a, b = knots[k:k+2]
        vals = [hermite(a[1][j], a[2][j], b[1][j], b[2][j], b[0]-a[0], t-a[0]) for j in range(3)]
        p = [origin[j]+vals[j][0] for j in range(3)]
        speed = [q[1] for q in vals]; acc = [q[2] for q in vals]
    tau = min(t, 14.)
    y = yaw + math.radians(30)*math.sin(math.pi*tau/14)**2
    yr = math.radians(30)*math.pi/14*math.sin(2*math.pi*tau/14) if t < 14 else 0.
    return p, speed, acc, y, yr


def global_waypoint(ned, ref_lat, ref_lon, ref_alt):
    """Small local route in GLOBAL_INT/MSL. Error negligible at this <10 m scale."""
    n, e, d = ned
    return (int(round((ref_lat+math.degrees(n/6371000.))*1e7)),
            int(round((ref_lon+math.degrees(e/(6371000.*math.cos(math.radians(ref_lat)))))*1e7)),
            ref_alt-d)


def in_gap(t):
    return GAP[0] <= t < GAP[1]


def budget(origin, velocity, yaw):
    rows = [trajectory(i*.01, origin, velocity, yaw) for i in range(1801)]
    radius = max(math.hypot(*r[0][:2]) for r in rows)
    heights = [-r[0][2] for r in rows]
    return dict(max_reference_radius_m=radius, min_reference_altitude_m=min(heights),
                max_reference_altitude_m=max(heights), reserve_m=1.,
                inside=radius+1. <= 8. and min(heights)>=2. and max(heights)<=5.)
