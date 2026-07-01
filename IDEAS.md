# Current NN Ideas

Allow for quadratic terms in the action, and incorporate a bilinear layer that considers terms like cos(theta_p)*sin(theta_p) or something like that.
Additionally, the inputs should actually be tuples of (cos(theta), sin(theta)) for each of the observables
Consider an L-EXP layer before the standard CNN that adjusts the fine lattice

# Radical Plaquette Based Idea
Use a naive blocking that preserves the 2x2 plaquette structure. Given this, determine the link variables such that they reproduce the same observables like rectangular loops and even topological charge. However, the main difficulty is how do you ensure that it is guage covariant.
The coarse graining does not need to make the fine lattice and coarse lattice guage equivalent. It just needs the physical observables to have the same distribution. Therefore, using something like a diffusion model to just preserve the observables is enough to necessitate this.
Additionally, any coarse lattice configuration with U(1) elements as links will transform properly such that any guage transformation will leave its physical observables (wilson loops/plaquettes) invariant. Therefore, any possible generation of these links that satisfy the observables conditions is enough. 
This diffusion model can be trained on the MMD between the observables distributions, and possibly tested on additional observables distributions that it is not trained on, or other batches of fine lattice configurations.