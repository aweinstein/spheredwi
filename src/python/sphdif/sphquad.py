"""Functions for spherical sampling and interpolation with proper quadratures.
"""
#-----------------------------------------------------------------------------
# Imports
#-----------------------------------------------------------------------------

# Third-party
import numpy as np
import matplotlib.pyplot as plt

norm = np.linalg.norm

#-----------------------------------------------------------------------------
# Functions definitions
#-----------------------------------------------------------------------------

def interp_matrix(qpnts, spnts, npgrid, nsamp, deg_max):
    """Create matrix associated with kernel interpolation.

    Parameters
    ----------
    qpnts = quadrature points
    spnts = sample points
    npgrid = number of points in grid
    nsamp  = number of sample points
    deg_max = maximum degree of spherical harmonic subspace
    """
    # Initialize
    A = np.zeros((nsamp,npgrid))

    # Create matrix
    for i in xrange(nsamp):
        for j in xrange(npgrid):
            cosTheta = np.dot(spnts[i], qpnts[j])
            if(abs(cosTheta)>1):
                cosTheta = np.sign(cosTheta)
            A[i,j] = inv_funk_radon_kernel(cosTheta, deg_max)
    return A


def rand_sig(u, b, n, theta):
    """Create random signal on the sphere

    Parameters
    ----------
      u = unit vector
      b = ?
      n = # of signal components
      theta = ?

     lambda1 = 1700e-6 mm^2/s --typical #s
     lambda2 =  300e-6  "
     lambda3 =  300e-6  "
           b = 3000 s/mm^2
    """
    # Locally used names
    from numpy import dot, exp

    # Diffusion tensor parameters
    lambda1 = 1700e-6
    lambda2 = 300e-6
    lambda3 = 300e-6

    rotationMatrix = rotation3Dz(theta)

    # diagonal diffusion tensor for "prolate white matter"
    D1 = np.diag([lambda1, lambda2, lambda3])
    D2 = np.diag([lambda1, lambda2, lambda3])
    D3 = D1

    # orthonormal e-vectors of diffusion tensor
    V1 = np.array([1, 0, 0, 0, 1, 0, 0, 0, 1], dtype=float).reshape(3, 3)
    V2 = np.array([1, 0, 0, 0, 1, 0, 0, 0, 1], dtype=float).reshape(3, 3)
    V3 = V1

    V2 = dot(rotationMatrix, V2)
    V3 = dot(rotationMatrix, dot(rotationMatrix, V3))

    # Change basis to diagonalize diffusion tensor
    u1p = dot(V1.T, u)
    u2p = dot(V2.T, u)
    u3p = dot(V3.T, u)

    # XXX - check with cory these semantics
    if n==1:
        s = exp(-b * dot(u1p, dot(D1,u1p)) )   # Single mode
    elif n==2:
        s = 0.5 * (exp(-b * dot(u1p, dot(D1,u1p)) ) +
                  exp(-b * dot(u2p, dot(D2,u2p)) ) )
    elif n==3:
        s = (1.0/3) * (exp(-b * dot(u1p, dot(D1,u1p)) ) +
                       exp(-b * dot(u2p, dot(D2,u2p)) ) +
                       exp(-b * dot(u3p, dot(D3,u3p)) ) )
    return s


def inv_funk_radon_kernel(mu, N):
    """Reproducing kernel

    Calculate the inverse Funk-Radon transform of reproducing kernel for the
    space of spherical harmonics of maximum degree N.

    Parameters
    ----------
        mu = cos(theta)   (a scaler)
         N = maximum degree of subspace
    """

    # Check that -1 <= mu <= 1
    mu = np.clip(mu, -1, 1)

    # Need Legendre polynomials
    legPolys = legp(mu, N)
    p_at_zero = legp(0, N)
    coefs = 2*np.arange(0, N+1, 2) + 1
    ker = coefs*legPolys[::2]/p_at_zero[::2]
    return ker.sum() / (8*np.pi)


def legp(x, n):
    """Legendre polynomials: calculation of Legendre polynomials up degree N

    Legendre polynomials up to and including degree N evaluated at x =
    cos(theta)

    Parameters
    ----------
      x : scalar or 1d array
        cos(theta)
      n : int
        highest degree

    Returns
    -------

    Array of polynomial evaluations.  If x was a 1d array of length p, the
    return array has shape (n, p).
    """
    if isinstance(x, np.ndarray):
        assert x.ndim==1, "x must be scalar or 1d array"
        shape = (n+1, x.shape[0])
    else:
        shape = (n+1, )
    p = np.zeros(shape)
    p[0] = 1
    if n<=1:
        return p
    p[1] = x
    for i in range(1, n):
        p[i+1] = ((2*i + 1)*x*p[i] - i*p[i-1] ) / (i+1)
    return p


def rotation3Dz(theta):
    """Create a 3D  rotation matrix for rotation about z-axis.
    """
    rmat = np.zeros((3,3))
    rmat[0,0] = rmat[1,1] = np.cos(theta)
    rmat[0,1] = np.sin(theta)
    rmat[1,0] = -rmat[0,1]
    rmat[2,2] = 1
    return rmat


def angle(x, y, deg=False):
    """Return angle between two vectors in R^3, in radians
    """
    rad_angle = np.arccos(np.dot(x, y)/ (norm(x)*norm(y)))
    if deg:
        return rad_angle*(180.0/np.pi)
    else:
        return rad_angle


def spherical_distances(x, y):
    """Compute the geodesic distance on the sphere for two points.

    The points are assumed to lie on the surface of the same sphere.

    Parameters
    ----------
    x : array [nptsx, 3]

    y : array [nptsy, 3]

    Returns
    -------
    dist : array [nptsx, nptsy]
    """
    # Compute the norms of all points, we do NOT check they actually all lie on
    # the same sphere (that's the caller's responsibility).
    
    xn = np.sqrt((x**2).sum(axis=1))
    yn = np.sqrt((y**2).sum(axis=1))
    ang_cos = np.dot(x, y.T)/(xn[:, None]*yn[None, :])
    # Protect against numerical noise giving us cosine values outside the -1,1
    # range, where arccos would return nans.
    ang_cos = np.clip(ang_cos, -1, 1)

    return xn[:, None]*np.arccos(ang_cos)


def estimate_bandwidth(X, quantile=0.3):
    """Estimate the bandwith ie the radius to use with an RBF kernel
    in the MeanShift algorithm

    X: array [n_samples, n_features]
        Input points

    quantile: float, default 0.3
        should be between [0, 1]
        0.5 means that the median is all pairwise distances is used
    """
    distances = spherical_distances(X, X)
    distances = np.triu(distances, 1)
    distances_sorted = np.sort(distances[distances > 0])
    bandwidth = distances_sorted[floor(quantile * len(distances_sorted))]
    return bandwidth


def mean_shift(X, bandwidth=None):
    """Perform MeanShift Clustering of data using a flat kernel

    Parameters
    ----------

    X : array [n_samples, n_features]
        Input points

    bandwidth : float, optional
        kernel bandwidth
        If bandwidth is not defined, it is set using
        a heuristic given by the median of all pairwise distances

    Returns
    -------

    cluster_centers : array [n_clusters, n_features]
        Coordinates of cluster centers

    labels : array [n_samples]
        cluster labels for each point

    Notes
    -----
    See examples/plot_meanshift.py for an example.

    K. Funkunaga and L.D. Hosteler, "The Estimation of the Gradient of a
    Density Function, with Applications in Pattern Recognition"

    """

    if bandwidth is None:
        bandwidth = estimate_bandwidth(X)

    n_points, n_features = X.shape

    n_clusters = 0
    bandwidth_squared = bandwidth**2
    points_idx_init = np.arange(n_points)
    stop_thresh = 1e-3*bandwidth # when mean has converged
    cluster_centers = [] # center of clusters
    # track if a points been seen already
    been_visited_flag = np.zeros(n_points, dtype=np.bool)
    # number of points to possibly use as initilization points
    n_points_init = n_points
    # used to resolve conflicts on cluster membership
    cluster_votes = []

    random_state = np.random.RandomState(0)

    while n_points_init:
        # pick a random seed point
        tmp_index = random_state.randint(n_points_init)
        # use this point as start of mean
        start_idx = points_idx_init[tmp_index]
        my_mean = X[start_idx, :] # intilize mean to this points location
        # points that will get added to this cluster
        my_members = np.zeros(n_points, dtype=np.bool)
        # used to resolve conflicts on cluster membership
        this_cluster_votes = np.zeros(n_points, dtype=np.uint16)

        while True: # loop until convergence

            # dist squared from mean to all points still active

            # FIXME - this needs to be converted to spherical distances.
            
            sqrt_dist_to_all = np.sum((my_mean - X)**2, axis=1)

            # points within bandwidth
            in_idx = sqrt_dist_to_all < bandwidth_squared
            # add a vote for all the in points belonging to this cluster
            this_cluster_votes[in_idx] += 1

            my_old_mean = my_mean # save the old mean
            my_mean = np.mean(X[in_idx, :], axis=0) # compute the new mean
            # add any point within bandwidth to the cluster
            my_members = np.logical_or(my_members, in_idx)
            # mark that these points have been visited
            been_visited_flag[my_members] = True

            if np.linalg.norm(my_mean-my_old_mean) < stop_thresh:

                # check for merge possibilities
                merge_with = -1
                for c in range(n_clusters):
                    # distance from possible new clust max to old clust max
                    dist_to_other = np.linalg.norm(my_mean -
                                                        cluster_centers[c])
                    # if its within bandwidth/2 merge new and old
                    if dist_to_other < bandwidth/2:
                        merge_with = c
                        break

                if merge_with >= 0: # something to merge
                    # record the max as the mean of the two merged
                    # (I know biased twoards new ones)
                    cluster_centers[merge_with] = 0.5 * (my_mean+
                                                cluster_centers[merge_with])
                    # add these votes to the merged cluster
                    cluster_votes[merge_with] += this_cluster_votes
                else: # its a new cluster
                    n_clusters += 1 # increment clusters
                    cluster_centers.append(my_mean) # record the mean
                    cluster_votes.append(this_cluster_votes)

                break

        # we can initialize with any of the points not yet visited
        points_idx_init = np.where(been_visited_flag == False)[0]
        n_points_init = points_idx_init.size # number of active points in set

    # a point belongs to the cluster with the most votes
    labels = np.argmax(cluster_votes, axis=0)

    return cluster_centers, labels