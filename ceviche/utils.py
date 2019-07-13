import numpy as np
import scipy.sparse as sp
import copy
import matplotlib.pylab as plt

from autograd import make_vjp
import autograd.numpy as npa

""" Just some utilities for easier testing and debugging"""

def make_sparse(N, random=True, density=1):
    """ Makes a sparse NxN matrix. """
    if not random:
        np.random.seed(0)
    D = sp.random(N, N, density=density) + 1j * sp.random(N, N, density=density)
    return D


def grad_num(fn, arg, step_size=1e-7):
    """ numerically differentiate `fn` w.r.t. its argument `arg` 
    `arg` can be a numpy array of arbitrary shape
    `step_size` can be a number or an array of the same shape as `arg` """

    N = arg.size
    shape = arg.shape
    gradient = np.zeros((N,))
    f_old = fn(arg)

    if type(step_size) == float:
        step = step_size*np.ones((N))
    else:
        step = step_size.ravel()

    for i in range(N):
        arg_new = copy.copy(arg.ravel())
        arg_new[i] += step[i]
        f_new_i = fn(arg_new.reshape(shape))
        gradient[i] = (f_new_i - f_old) / step[i]

    return gradient.reshape(shape)

def circ2eps(x, y, r, eps_c, eps_b, dL):
    """ Define eps_r through circle parameters """
    shape = eps_b.shape   # shape of domain (in num. grids)
    Nx, Ny = (shape[0], shape[1])

    # x and y coordinate arrays
    x_coord = np.linspace(-Nx/2*dL, Nx/2*dL, Nx)
    y_coord = np.linspace(-Ny/2*dL, Ny/2*dL, Ny)

    # x and y mesh
    xs, ys = np.meshgrid(x_coord, y_coord, indexing='ij')

    eps_r = copy.copy(eps_b)
    for ih in range(x.shape[0]):
        mask = (xs - x[ih])**2 + (ys - y[ih])**2 < r[ih]**2
        eps_r[mask] = eps_c[ih]

    return eps_r


def grid_coords(array, dL):
    # Takes an array and returns the coordinates of the x and y points

    shape = Nx, Ny = array.shape   # shape of domain (in num. grids)

    # x and y coordinate arrays
    x_coord = np.linspace(-Nx/2*dL, Nx/2*dL, Nx)
    y_coord = np.linspace(-Ny/2*dL, Ny/2*dL, Ny)

    # x and y mesh
    xs, ys = np.meshgrid(x_coord, y_coord, indexing='ij')

    return xs, ys

""" Autograd Stuff """

def vjp_maker_num(fn, arg_inds, steps):
    """ Makes a vjp_maker for the numerical derivative of a function `fn`
    w.r.t. argument at position `arg_ind` using step sizes `steps` """

    def vjp_single_arg(ia):
        arg_ind = arg_inds[ia]
        step = steps[ia]

        def vjp_maker(fn_out, *args):
            shape = args[arg_ind].shape
            num_p = args[arg_ind].size
            step = steps[ia]

            def vjp(v):

                vjp_num = np.zeros(num_p)
                for ip in range(num_p):
                    args_new = list(args)
                    args_rav = args[arg_ind].flatten()
                    args_rav[ip] += step
                    args_new[arg_ind] = args_rav.reshape(shape)
                    dfn_darg = (fn(*args_new) - fn_out)/step
                    vjp_num[ip] = np.sum(v * dfn_darg)

                return vjp_num

            return vjp

        return vjp_maker

    vjp_makers = []
    for ia in range(len(arg_inds)):
        vjp_makers.append(vjp_single_arg(ia=ia))

    return tuple(vjp_makers)

from autograd.core import make_vjp as _make_vjp, make_jvp as _make_jvp
from autograd.wrap_util import unary_to_nary
from autograd.extend import primitive, defvjp_argnum, vspace

@unary_to_nary
def jacobian_forward(fn, x):
    """
    Returns a function which computes the Jacobian of `fun` with respect to
    positional argument number `argnum`, which must be a scalar or array. Unlike
    `grad` it is not restricted to scalar-output functions, but also it cannot
    take derivatives with respect to some argument types (like lists or dicts).
    If the input to `fun` has shape (in1, in2, ...) and the output has shape
    (out1, out2, ...) then the Jacobian has shape (out1, out2, ..., in1, in2, ...).
    """
    vjp, ans = _make_vjp(fun, x)
    ans_vspace = vspace(ans)
    jacobian_shape = ans_vspace.shape + vspace(x).shape
    grads = map(vjp, ans_vspace.standard_basis())
    return np.reshape(np.stack(grads), jacobian_shape)





""" Plotting and measurement utilities for FDTD, may be moved later"""


def aniplot(F, source, steps, component='Ez', num_panels=10):
    """ Animate an FDTD (F) with `source` for `steps` time steps.
    display the `component` field components at `num_panels` equally spaced.
    """
    F.initialize_fields()

    # initialize the plot
    f, ax_list = plt.subplots(1, num_panels, figsize=(20*num_panels,20))
    Nx, Ny, _ = F.eps_r.shape
    ax_index = 0

    # fdtd time loop
    for t_index in range(steps):
        fields = F.forward(Jz=source(t_index))
    
        # if it's one of the num_panels panels
        if t_index % (steps // num_panels) == 0:
            print('working on axis {}/{} for time step {}'.format(ax_index, num_panels, t_index))

            # grab the axis
            ax = ax_list[ax_index]

            # plot the fields
            im_t = ax.pcolormesh(np.zeros((Nx, Ny)), cmap='RdBu')
            max_E = np.abs(fields[component]).max()
            im_t.set_array(fields[component][:, :, 0].ravel().T)
            im_t.set_clim([-max_E / 2.0, max_E / 2.0])
            ax.set_title('time = {} seconds'.format(F.dt*t_index))

            # update the axis
            ax_index += 1


def measure_fields(F, source, steps, probes, component='Ez'):
    """ Returns a time series of the measured `component` fields from FDFD `F`
        driven by `source and measured at `probe`.
    """
    F.initialize_fields()
    if not isinstance(probes, list):
        probes = [probes]
    N_probes = len(probes)
    measured = np.zeros((steps, N_probes))
    for t_index in range(steps):
        if t_index % (steps//20) == 0:
            print('{:.2f} % done'.format(float(t_index)/steps*100.0))
        fields = F.forward(Jz=source(t_index))
        for probe_index, probe in enumerate(probes):
            field_probe = np.sum(fields[component] * probe)
            measured[t_index, probe_index] = field_probe
    return measured

""" FFT Utilities """

from numpy.fft import fft, fftfreq
from librosa.core import stft
from librosa.display import specshow

def get_spectrum(series, dt):
    """ Get FFT of series """

    steps = len(series)
    times = np.arange(steps) * dt

    # reshape to be able to multiply by hamming window
    series = series.reshape((steps, -1))

    # multiply with hamming window to get rid of numerical errors
    hamming_window = np.hamming(steps).reshape((steps, 1))
    signal_f = np.fft.fft(hamming_window * series)

    freqs = np.fft.fftfreq(steps, d=dt)
    return freqs, signal_f

def get_max_power_freq(series, dt):

    freqs, signal_f = get_spectrum(series, dt)
    return freqs[np.argmax(signal_f)]

def get_spectral_power(series, dt):

    freqs, signal_f = get_spectrum(series, dt)
    return freqs, np.square(np.abs(signal_f))

def plot_spectral_power(series, dt, f_top=2e14):
    steps = len(series)
    freqs, signal_f_power = get_spectral_power(series, dt)

    # only plot half (other is redundant)
    plt.plot(freqs[:steps//2], signal_f_power[:steps//2])
    plt.xlim([0, f_top])
    plt.xlabel('frequency (Hz)')
    plt.ylabel('power (|signal|^2)')
    plt.show()