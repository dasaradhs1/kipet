#  _________________________________________________________________________
#
#  Kipet: Kinetic parameter estimation toolkit
#  Copyright (c) 2016 Eli Lilly.
#  _________________________________________________________________________

# Sample Problem
# Estimation with unknow variancesof spectral data using pyomo discretization
#
#		\frac{dZ_a}{dt} = -k_1*Z_a	                Z_a(0) = 1
#		\frac{dZ_b}{dt} = k_1*Z_a - k_2*Z_b		Z_b(0) = 0
#               \frac{dZ_c}{dt} = k_2*Z_b	                Z_c(0) = 0
#               C_k(t_i) = Z_k(t_i) + w(t_i)    for all t_i in measurement points
#               D_{i,j} = \sum_{k=0}^{Nc}C_k(t_i)S(l_j) + \xi_{i,j} for all t_i, for all l_j
#       Initial concentration

from __future__ import print_function
from kipet.library.TemplateBuilder import *
from kipet.library.PyomoSimulator import *
from kipet.library.ParameterEstimator import *
from kipet.library.VarianceEstimator import *
from kipet.library.data_tools import *
import matplotlib.pyplot as plt
import os
import sys
import inspect
import six

if __name__ == "__main__":

    with_plots = True

    if len(sys.argv) == 2:
        if int(sys.argv[1]):
            with_plots = False

    # =========================================================================
    # USER INPUT SECTION - REQUIRED MODEL BUILDING ACTIONS
    # =========================================================================

    # Load spectral data from the relevant file location. As described in section 4.3.1
    #################################################################################
    dataDirectory = os.path.abspath(
        os.path.join(os.path.dirname(os.path.abspath(inspect.getfile(
            inspect.currentframe()))), 'data_sets'))
    filename = os.path.join(dataDirectory, 'Dij.txt')
    D_frame = read_spectral_data_from_txt(filename)

    # Then we build dae block for as described in the section 4.2.1. Note the addition
    # of the data using .add_spectral_data
    #################################################################################
    builder = TemplateBuilder()
    components = {'A': 1e-3, 'B': 0, 'C': 0}
    builder.add_mixture_component(components)
    builder.add_parameter('k1', init=4.0, bounds=(0.0, 5.0))
    # There is also the option of providing initial values: Just add init=... as additional argument as above.
    builder.add_parameter('k2', bounds=(0.0, 1.0))
    builder.add_spectral_data(D_frame)


    # define explicit system of ODEs
    def rule_odes(m, t):
        exprs = dict()
        exprs['A'] = -m.P['k1'] * m.Z[t, 'A']
        exprs['B'] = m.P['k1'] * m.Z[t, 'A'] - m.P['k2'] * m.Z[t, 'B']
        exprs['C'] = m.P['k2'] * m.Z[t, 'B']
        return exprs


    builder.set_odes_rule(rule_odes)
    builder.bound_profile(var='S', bounds=(0, 200))
    opt_model = builder.create_pyomo_model(0.0, 10.0)

    # =========================================================================
    # USER INPUT SECTION - VARIANCE ESTIMATION
    # =========================================================================
    # For this problem we have an input D matrix that has some noise in it
    # If we have the situation where model noise can be neglected, KIPET can still be used!
    # for this case we first calculate the variance of the device, using the function:
    # solve_max_device_variance
    v_estimator = VarianceEstimator(opt_model)
    v_estimator.apply_discretization('dae.collocation', nfe=100, ncp=1, scheme='LAGRANGE-RADAU')

    # It is often requried for larger problems to give the solver some direct instructions
    # These must be given in the form of a dictionary
    options = {}
    # While this problem should solve without changing the deault options, example code is
    # given commented out below. See Section 5.6 for more options and advice.
    # options['bound_push'] = 1e-8
    # options['tol'] = 1e-9

    # Finally we run the variance estimatator using the arguments shown in Seciton 4.3.3
    worst_case_device_var = v_estimator.solve_max_device_variance('ipopt',
                                                                  tee=False,
                                                                  # subset_lambdas = A_set,
                                                                  solver_opts=options)

    # following this, we can solve the parameter estimation problem
    # =========================================================================
    # USER INPUT SECTION - PARAMETER ESTIMATION
    # =========================================================================
    # In order to run the paramter estimation we create a pyomo model as described in section 4.3.4
    # opt_model = builder.create_pyomo_model(0.0,10.0)

    # and define our parameter estimation problem and discretization strategy
    p_estimator = ParameterEstimator(opt_model)
    # p_estimator.apply_discretization('dae.collocation',nfe=100,ncp=1,scheme='LAGRANGE-RADAU')

    # Again we provide options for the solver, this time providing the scaling that we set above
    options = dict()
    # options['nlp_scaling_method'] = 'user-scaling'
    # options['linear_solver'] = 'ma57'

    # Since, for this case we only need delta and not the model variance, we add the additional option
    # to exclude model variance and then run the optimization
    results_pyomo = p_estimator.run_opt('k_aug',
                                        tee=False,
                                        model_variance=False,
                                        solver_opts=options,
                                        variances=worst_case_device_var,
                                        covariance=True)
    p_estimator.model.display(filename='filemodel.txt')

    # And display the results
    print("The estimated parameters are:")
    for k, v in six.iteritems(results_pyomo.P):
        print(k, v)
    

    # display results
    if with_plots:
        results_pyomo.Z.plot.line(legend=True)
        plt.xlabel("time (s)")
        plt.ylabel("Concentration (mol/L)")
        plt.title("Concentration Profile")

        results_pyomo.S.plot.line(legend=True)
        plt.xlabel("Wavelength (cm)")
        plt.ylabel("Absorbance (L/(mol cm))")
        plt.title("Absorbance  Profile")
        plt.show()