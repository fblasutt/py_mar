#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
This collects routines for renegotiation and marriage

Some code is meant to be reused

"""


from trans_unif import transition_uniform
import numpy as np
from aux_routines import first_true, last_true, zero_hit_mat
from numba import njit

# this is renegotiator
# this accounts for divorce protocol
def v_ren(setup,V,interpolate=True):
    # this returns value functions for couple that entered the last period with
    # (s,Z,theta) from the grid and is allowed to renegotiate them or breakup
    
    dc = setup.div_costs
    
    sc = setup.agrid # savings of couple are given by the agrid
    
    
    assert (dc.money_lost_f_ez == 0 and dc.money_lost_m_ez == 0), 'not implemented yet'
    
    sf = dc.assets_kept*0.5*sc - dc.money_lost_f
    sm = dc.assets_kept*0.5*sc - dc.money_lost_m
    
    ism, psm = transition_uniform(setup.agrid,sm)
    isf, psf = transition_uniform(setup.agrid,sf)
    
    psm, psf = (x[:,None] for x in (psm, psf))
    
    ind, izf, izm, ipsi = setup.all_indices()
    
    
    VMval_single, VFval_single = V['Male, single']['V'], V['Female, single']['V']
    Vval_postren, VMval_postren, VFval_postren = V['Couple']['V'], V['Couple']['VM'], V['Couple']['VF']
    
    
    is_unil = dc.unilateral_divorce # whether to do unilateral divorce at all
    
    Vm_divorce = (VMval_single[ism,:]*psm + VMval_single[ism+1,:]*(1-psm))[:,izm] - dc.u_lost_m
    Vf_divorce = (VFval_single[isf,:]*psf + VFval_single[isf+1,:]*(1-psf))[:,izf] - dc.u_lost_f
    
    assert Vval_postren.shape[:-1] == Vm_divorce.shape
    
    outs = v_prepare(VFval_postren,VMval_postren,Vval_postren,Vf_divorce,Vm_divorce,setup.thetagrid,interpolate=interpolate)
    # this is syntactically dirty but efficient
    return v_ren_core(*outs,interpolate=interpolate,unilateral=is_unil)

def v_mar(setup,V,sf,sm,ind_or_inds,interpolate=True,return_all=False):
    # this returns value functions for couple that entered the last period with
    # (s,Z,theta) from the grid and is allowed to renegotiate them or breakup
    
    # if return_all==False returns Vout_f, Vout_m, that are value functions
    # of male and female from entering this union
    # if return_all==True returns (Vout_f, Vout_m, ismar, thetaout, technical)
    # where ismar is marriage decision, thetaout is resulting theta and 
    # tuple technical contains less usable stuff (check v_newmar_core for it)
    
    
    agrid = setup.agrid
    gamma = setup.pars['m_bargaining_weight']    
    VMval_single, VFval_single = V['Male, single']['V'], V['Female, single']['V']
    Vval_postren, VMval_postren, VFval_postren = V['Couple']['V'], V['Couple']['VM'], V['Couple']['VF']
    
    
    # substantial part
    ind, izf, izm, ipsi = setup.all_indices(ind_or_inds)
    
    
    sc = sf+sm # savings of couple
    
    # this finds weight and indices for interpolation of sf, sm and sc on agrid
    # note that transition_uniform implicitly trims things on top,
    # so if sf is 0.75*amax and sm is 0.75*amax then sc is 1*amax and not 1.5
    
    isf, psf = transition_uniform(agrid,sf)
    ism, psm = transition_uniform(agrid,sm)
    isc, psc = transition_uniform(agrid,sc)
    
    ism, isf, isc, psf, psm, psc = (x[:,None] for x in (ism,isf,isc,psf, psm, psc))
    
    
    Vms = VMval_single[ism,izm]*psm + VMval_single[ism+1,izm]*(1-psm)
    Vfs = VFval_single[isf,izf]*psf + VFval_single[isf+1,izf]*(1-psf)
    Vmm = VMval_postren[isc,ind,:]*(psc[:,:,None]) + VMval_postren[isc+1,ind,:]*(1-psc[:,:,None])
    Vfm = VFval_postren[isc,ind,:]*(psc[:,:,None]) + VFval_postren[isc+1,ind,:]*(1-psc[:,:,None])
    Vcm = Vval_postren[isc,ind,:]*(psc[:,:,None])  +  Vval_postren[isc+1,ind,:]*(1-psc[:,:,None])
    
    
    outs = v_prepare(Vfm,Vmm,Vcm,Vfs,Vms,setup.thetagrid,interpolate=interpolate)
    # this is syntactically dirty but efficient
    return v_newmar_core(*outs,interpolate=interpolate,gamma=gamma,return_all=return_all)


def v_prepare(VF_yes,VM_yes,VC_yes,VF_no,VM_no,thetagrid,interpolate=False):
    # this takes value functions of females, males and couples in case of being 
    # together and divorce and looks for their values around the points where
    # outside options are hit (VF_t,VM_t,V_t), positions between gridpoints 
    # where linearly interpolated value is exactly equal to outside options
    # (that are in k_t), points where people agree to be together as it is
    # (that is in I_t). Finally it packs input agruments too. 
    # After this it can be passed to a funciton describing creation of new 
    # marriages or renegotiation, as both of these processes require such 
    # prepartation. 
    # If interpolate=False it does not allow for theta to be somewhere between
    # thetagrid, hence most of the outputs are actually useless. 
    
    
    ax = VC_yes.ndim - 1 # axis where theta is
    nt = VC_yes.shape[ax] # number of thetas
    
    assert nt==thetagrid.size
    
    #print((ax,nt))
    
    shp = VF_yes.shape[:-1] + (1,)
    
    VF_no_r = VF_no.reshape(shp)
    VM_no_r = VM_no.reshape(shp)
    
    S_f = VF_yes - VF_no_r # surplus of female
    S_m = VM_yes - VM_no_r # surplus of male
    
   #print(S_f.shape,S_m.shape)
    
    I_f = np.array(S_f > 0) # whether female agrees at this gridpoint
    I_m = np.array(S_m > 0) # whether male agrees at this gridpoint
    
    
    sq = (I_f & I_m)
    
    
    nf = first_true(I_f,axis=ax)
    nm = last_true(I_m,axis=ax)
    
    together = np.any(sq,axis=ax)
    
    
    
    
    together_2 = (np.array(nf<=nm) & np.array(nf!=-1) & np.array(nm!=-1) )
    
    on_the_edge = (np.array(nf == nm+1) & np.array(nf!=-1) & np.array(nm!=-1) ).reshape(shp)
    
    assert np.all(together_2 == together)
    
    
    NF = nf.reshape(shp)
    NF_fix = np.array( NF == 0 ) # when first true is zero
    NF[NF_fix] = 1
    NF_ok = np.array( NF != -1 ) # when there is at least some true value
    NF_sc = (NF_ok & ~NF_fix) # whether it corresponds to sign change
    NF[~NF_ok] = nt-1
    
    
    
    NM = nm.reshape(shp)
    NM_fix = np.array( NM == nt-1)
    NM[NM_fix] = nt-2
    NM_ok = np.array(NM != -1)
    NM[~NM_ok] = 0
    NM_sc = (NM_ok & ~NM_fix)
    
    
    # rf is theta grid poisition to the right of point where female surplus intersects zero
    # (so it is positive as surplus is increasing in theta)
    # lf is to the left (so it is negative)
    # rm is theta grid poisition to the right of point where male surplus intersects zero
    # (so it is negative)
    # lm is to the left (so it is positive)
    
    # if renegotiated female-induced: move to rf
    # if renegotiated male-induced: move to lm
    # lf and rm are technical for interpolation
    
    rf, lf, rm, lm  = NF, NF-1, NM+1, NM
    
    VF_rf, VF_lf, VF_rm, VF_lm  = (np.take_along_axis(VF_yes,x,ax) for x in (rf, lf, rm, lm))
    VM_rf, VM_lf, VM_rm, VM_lm =  (np.take_along_axis(VM_yes,x,ax) for x in (rf, lf, rm, lm))
    VC_rf, VC_lf, VC_rm, VC_lm =  (np.take_along_axis(VC_yes,x,ax) for x in (rf, lf, rm, lm))
    

    A_l, A_r = VF_lf - VF_no_r, VF_rf - VF_no_r
    B_l, B_r = VM_lm - VM_no_r, VM_rm - VM_no_r
    
    assert np.all(A_r[NF_sc]>0)
    assert np.all(A_l[NF_sc]<0)
    assert np.all(B_l[NM_sc]>0)
    assert np.all(B_r[NM_sc]<0)
    
    
    kr_f = -A_l/(A_r - A_l)    
    kr_m = B_l/(B_l - B_r) 
    kr_f[NF_fix] = 0.0
    kr_m[NF_fix] = 1.0
    
    
    #Kf, loc, kf = zero_hit_mat(S_f, return_loc=True)
    #print(kf-kr_f)
    #assert np.all(kf==kr_f)
    
    
    # out of NF_sc these values do not make much sense
    
    assert np.max(np.abs( (A_l*(1-kr_f) + A_r*kr_f)[NF_sc] )) < 1e-4
    assert np.max(np.abs( (B_l*(1-kr_m) + B_r*kr_m)[NM_sc] )) < 1e-4
    
    assert np.all(kr_f[NF_sc]>=0) and np.all(kr_f[NF_sc]<=1)
    assert np.all(kr_m[NM_sc]>=0) and np.all(kr_m[NM_sc]<=1)
    
    
    on_the_edge_y = np.full_like(on_the_edge,False)
    on_the_edge_y[(np.array(kr_f <= kr_m) & on_the_edge)] = True
    
    if np.any(on_the_edge_y):
        assert np.all( (B_l*(1-kr_f) + B_r*kr_f)[on_the_edge_y] >= 0 ) 
        assert np.all( (A_l*(1-kr_m) + A_r*kr_m)[on_the_edge_y] >= 0 )
        
    
    
    if interpolate:
        together = (together | on_the_edge_y.squeeze())
        
        
    ### this part computes things relevant for bilateral divorce
    
    # for bilateral divorce we cannot really use interpolation
    # we only compute couple's value function in particular theta and this 
    # theta does not move (so there is no way to have between-point theta 
    # although at the moment of marriage we get between-point theta). 
    # this should not matter too much if we have enough points for theta or 
    # enough points for psi, though this will underestimate the hazard of 
    # bilateral divorce
    
    I_both_disagree = (~I_f) & (~I_m)
    
    ### 
    
    
    # where outside options are hit
    VF_t = (VF_rf, VF_lf, VF_rm, VF_lm) 
    VM_t = (VM_rf, VM_lf, VM_rm, VM_lm)
    VC_t = (VC_rf, VC_lf, VC_rm, VC_lm)
    kr_t  = (kr_f, kr_m)
    N_t   = (NF_sc,NM_sc,NF_ok,NM_ok,NF,NM)
    I_t   = (I_f, I_m)
    yes_t = (VF_yes,VM_yes,VC_yes)
    no_t = (VF_no, VM_no)
    BD_t = (I_both_disagree,) # comma indicates one-element tuple
    
    
    
    # this seems to return too much
    return VF_t, VM_t, VC_t, kr_t, N_t, I_t, yes_t, no_t, BD_t, together, thetagrid, shp

    
def v_ren_core(VF_t,VM_t,VC_t,kr_t,N_t,I_t,yes_t,no_t,BD_t,together,thetagrid,shp, interpolate=True, unilateral=True):
    # this takes output of v_prepare as input and returns the results of renegotiation
    # The results are of the same shape as VF_yes, VM_yes, VC_yes that we feed
    # to v_prepare.
    
    nt = thetagrid.size
    
    (VF_rf, VF_lf, VF_rm, VF_lm) = VF_t
    (VM_rf, VM_lf, VM_rm, VM_lm) = VM_t
    (VC_rf, VC_lf, VC_rm, VC_lm) = VC_t
    (kr_f, kr_m) = kr_t
    (NF_sc,NM_sc,NF_ok,NM_ok,NF,NM) = N_t
    (I_f, I_m) = I_t
    (VF_no, VM_no) = no_t
    (VF_yes,VM_yes,VC_yes) = yes_t
    (I_both_disagree,) = BD_t
    
    VF_no_r = VF_no.reshape(shp)
    VM_no_r = VM_no.reshape(shp)
    
    f_ren = (~I_f & together.reshape(shp)) # female-initiated renegotiation
    m_ren = (~I_m & together.reshape(shp)) # male-initiated renegotiation
     
    
    
    # I create new for preren
    VF_out = np.copy(VF_yes)
    VM_out = np.copy(VM_yes)
    V_out  = np.copy(VC_yes)
    
    
    
    if not interpolate:
        Vf_ifren_f = VF_rf
        Vf_ifren_m = VF_lm
        Vm_ifren_f = VM_rf
        Vm_ifren_m = VM_lm
        V_ifren_f  = VC_rf
        V_ifren_m  = VC_lm
    
    else:
        
        # when no agreement kr_f and kr_m are bullshit
        # this is alright as we do use only those that
        # are in f_ren and m_ren regions where there is an agreement
        
        Vf_ifren_f = (1-kr_f)*VF_lf + kr_f*VF_rf
        Vm_ifren_f = (1-kr_f)*VM_lf + kr_f*VM_rf
        V_ifren_f  = (1-kr_f)*VC_lf + kr_f*VC_rf
        
        Vf_ifren_m = (1-kr_m)*VF_lm + kr_m*VF_rm
        Vm_ifren_m = (1-kr_m)*VM_lm + kr_m*VM_rm
        V_ifren_m  = (1-kr_m)*VC_lm + kr_m*VC_rm
        
        
        
        
        assert np.all( np.abs( Vf_ifren_f - VF_no_r)[NF_sc] < 1e-4 )
        assert np.all( np.abs( Vm_ifren_m - VM_no_r)[NM_sc] < 1e-4 )
        
        
        
        
    bt = lambda x : np.broadcast_to(x, VF_out.shape) # mad skillz
    # this assumed VF_out and VM_out have the same shape
    
    tshape = (VF_yes.ndim-1)*(1,) + (nt,)
    
    t_stretch = bt(thetagrid.reshape(tshape))
    
    
    
    
    if unilateral:
        
        #### this does unilateral divorce (working scenario)
        
        
        bool_divorce = bt(~together.reshape(shp))
        VF_out[bool_divorce] = bt(VF_no_r)[bool_divorce]
        VM_out[bool_divorce] = bt(VM_no_r)[bool_divorce]
        
        V_out[bool_divorce] = t_stretch[bool_divorce]*VF_out[bool_divorce] + \
                          (1-t_stretch[bool_divorce])*VM_out[bool_divorce] # check me please
        
        VF_out[f_ren] = bt(Vf_ifren_f)[f_ren]
        VM_out[f_ren] = bt(Vm_ifren_f)[f_ren]
        V_out[f_ren]  = bt( V_ifren_f)[f_ren]
        
        VF_out[m_ren] = bt(Vf_ifren_m)[m_ren]
        VM_out[m_ren] = bt(Vm_ifren_m)[m_ren]
        V_out[m_ren]  = bt( V_ifren_m)[m_ren]
        
        assert np.all(VF_out >= VF_no_r - 1e-4)
        assert np.all(VM_out >= VM_no_r - 1e-4)
    
    else:
        #### this section capures bilateral divorce
        #### above we compute some things that are not relevant to it but this
        #### is ok as this is not intended to be used extensively
        
        i = I_both_disagree
        bVF_no, bVM_no = bt(VF_no_r), bt(VM_no_r) # broadcast to match the shape
        VF_out[i] = bVF_no[i]
        VM_out[i] = bVM_no[i]
        V_out[i]  = t_stretch[i]*bVF_no[i] + (1-t_stretch[i])*bVM_no[i]
        
    
    return V_out, VF_out, VM_out


def v_newmar_core(VF_t,VM_t,VC_t,kr_t,N_t,I_t,yes_t,no_t,BD_t,together,thetagrid,shp,gamma=0.5,interpolate=False,return_all=False):
    # this takes output of v_prepare and computes value function that is obtained
    # in new marriage. The result is of the same shape as VF_no or VM_no
    # 
    
    ntheta = thetagrid.size
    
    (VF_rf, VF_lf, VF_rm, VF_lm) = VF_t
    (VM_rf, VM_lf, VM_rm, VM_lm) = VM_t
    (VC_rf, VC_lf, VC_rm, VC_lm) = VC_t
    (kr_f, kr_m) = kr_t
    (NF_sc,NM_sc,NF_ok,NM_ok,NF,NM) = N_t
    (I_f, I_m) = I_t
    (VF_no, VM_no) = no_t
    (VF_yes,VM_yes,VC_yes) = yes_t
    
    
    VF_no_r = VF_no.reshape(shp)
    VM_no_r = VM_no.reshape(shp)
    
    s_f = VF_yes - VF_no_r
    s_m = VM_yes - VM_no_r # broadcasted
    
    assert s_f.shape == VF_yes.shape
    assert s_f.shape[:-1] == VM_no.shape
    
    nbs = np.full_like(s_m,-np.inf)
    
    Vout_m, Vout_f = np.empty_like(VM_no), np.empty_like(VM_no)
        
    
    
    i_pos = (I_m & I_f)
    nbs[i_pos] = s_m[i_pos]**(gamma) * s_f[i_pos]**(1-gamma)
    nbs_best_g = nbs.max(axis=2)
    nbs_best_g = nbs_best_g[nbs_best_g>0]
    
    
    if not interpolate:
        i_pos = (I_m & I_f)
        nbs[i_pos] = s_m[i_pos]**(gamma) * s_f[i_pos]**(1-gamma)
        ismar = np.any(nbs>0,axis=2)
        i_theta  = nbs[ismar,:].argmax(axis=1) - 1
        wn_theta = np.ones_like(i_theta,dtype=np.float32)
    
    else:
        # mixing boolean indexing waaaaith : produces 2-dimensional array instead
        # of 3-dimensional: first dimension is Matlab-ordered version
        # of boolean variable. 
        
        im_good = (NF<=NM).squeeze()
        fixed_good = ((NF==NM+1).squeeze()) & ((kr_f+0.1<=kr_m).squeeze())
        any_good = (im_good) | (fixed_good)
        ii_theta = np.full(any_good.shape,np.nan,dtype=np.int32)
        iwn_theta = np.full(any_good.shape,np.nan,dtype=np.float32)
        iwn_theta[fixed_good] = ((kr_f*(1-gamma) + kr_m*gamma).squeeze())[fixed_good]
        ii_theta[fixed_good] = NF.squeeze()[fixed_good]
        
        n_rows = np.sum(any_good)
        
        shp = (n_rows,ntheta)
        
        sm_res = s_m.copy()[any_good,:].reshape(shp)
        sf_res = s_f.copy()[any_good,:].reshape(shp)
        
        
        
        
        i_theta, wn_theta, nbsv = max_nbs_mat(sf_res,sm_res,gamma)
        
        
        ismar = any_good
            
    
    if np.any(~ismar):
        Vout_m[~ismar] = VM_no[~ismar]
        Vout_f[~ismar] = VF_no[~ismar]
    
    if np.any(ismar):
        Vout_m[ismar]  = VM_yes[ismar,i_theta]*(1-wn_theta) + VM_yes[ismar,i_theta+1]*wn_theta
        Vout_f[ismar]  = VF_yes[ismar,i_theta]*(1-wn_theta) + VF_yes[ismar,i_theta+1]*wn_theta
    
    if not return_all:
        return Vout_f, Vout_m 
    else:
        thetaout = np.full_like(VF_no,np.nan)
    
        if np.any(ismar):
            thetaout[ismar] = thetagrid[i_theta]*(1-wn_theta) + thetagrid[i_theta+1]*wn_theta
        
        technical = (i_theta,wn_theta,nbsv,VM_yes,VM_no,VF_yes,VF_no)
        
        return Vout_f, Vout_m, ismar, thetaout, technical


from optimizers import build_s_grid, sgrid_on_agrid


def max_nbs_interp(sf,sm,theta_grid,gamma):
    assert sf.shape[1] == theta_grid.size
    assert sf.ndim == sm.ndim == 2
    thteta_grid_expanded = build_s_grid(theta_grid,10,0.001,0.01)
    ind, p = sgrid_on_agrid(thteta_grid_expanded,theta_grid)
    
    sm_expanded = sm[:,ind]*(1-p[None,:]) + sm[:,ind+1]*p[None,:]
    sf_expanded = sf[:,ind]*(1-p[None,:]) + sf[:,ind+1]*p[None,:]
    nbs = np.full_like(sm_expanded,-np.inf)
    i_pos = (sm_expanded>0) & (sf_expanded>0)
    nbs[i_pos] = ((sm_expanded[i_pos])**gamma) * ((sf_expanded[i_pos])**(1-gamma))
    #print(np.mean(~np.any(nbs>0,axis=1)))
    assert np.all(np.any(nbs>0,axis=1))
    io = nbs.argmax(axis=1)
    nbsv = np.take_along_axis(nbs.copy(),io[:,None],axis=1).flatten()
    itheta = ind[io]
    wntheta = p[io]
    return itheta, wntheta, nbsv
    

        
# this is a vectorized version
def max_nbs_mat(sf,sm,gamma):
    # this is vectorized version of max_nbs
    
    assert np.all(sf!=0.0) # it's hard to get exactly 0 right
    assert np.all(sm!=0.0) # some parts break in this case
    
    assert sf.shape == sm.shape
    assert sf.ndim == 2
    
    # the code operates using "now" and "before" points so last dimension is 
    # decreased by 1
    
    shp = (sf.shape[0],sf.shape[1]-1)
    
    nbs_mat, nbs_bef, nbs_now = (np.full(shp,-np.inf,dtype=np.float64) for _ in (0,1,2))
    ws_mat  = np.empty(shp, dtype=np.float64)
    
    sf_bef = sf[:,:-1]
    sf_now = sf[:,1:]
    sm_bef = sm[:,:-1]
    sm_now = sm[:,1:]
    
    dsf     = sf_now - sf_bef
    neg_dsm = sm_bef - sm_now
    
    kf = sf_bef / (-dsf)
    km = sm_bef / (neg_dsm)
    
    assert np.all(dsf>0) and np.all(neg_dsm>0),     'check monotonicity'
    
    
    i_both_pos_now = (sf_now>0) & (sm_now>0)
    i_both_pos_bef = (sf_bef>0) & (sm_bef>0)

    
    nbs_now[i_both_pos_now] = (sf_now[i_both_pos_now])**(gamma) * (sm_now[i_both_pos_now])**(1-gamma)
    nbs_bef[i_both_pos_bef] = (sf_bef[i_both_pos_bef])**(gamma) * (sm_bef[i_both_pos_bef])**(1-gamma)
    
    #assert np.all(nbs_now[i_both_pos_now]>0) and np.all(nbs_bef[i_both_pos_bef]>0)
    
    # we will need this later
    # this is numpy fix as it does not handle two bool indices nicely
    # here m1 and m2 are boolean masks. basically a[tm(m1,m2)] is a[m1][m2],
    # but the former a[m1][m2] = b does not change values of a b/c of numpy
    # practice to make copies of the data for the case of boolean indexing
    tm = lambda m1, m2 : tuple([a[m2] for a in np.where(m1)])
    
    
    
    # there are five cases conceptually
    
    
    
    i_no_hope    = (sf_now < 0) | (sm_bef < 0) # negotiation is impossible, notice |
    i_both_happy = (sf_bef > 0) & (sm_now > 0)    
    i_both_edge  = (sf_bef < 0) & (sf_now > 0) & (sm_now < 0) & (sm_bef > 0)
    i_fem_edge   = (sf_bef < 0) & (sf_now > 0) & (sm_now > 0) & (sm_bef > 0)
    i_mal_edge   = (sf_bef > 0) & (sf_now > 0) & (sm_now < 0) & (sm_bef > 0)
    
    
    alpha = np.full(shp,np.nan,dtype=np.float64)
    
    # both happy - just find alanlytical solutuion
    
    i = i_both_happy
    alpha[i] = (gamma*(sm_bef[i]/neg_dsm[i]) - (1-gamma)*(sf_bef[i]/dsf[i]))    
    #assert np.all(~np.isinf(nbs_bef[i]))        
    #assert np.all(~np.isinf(nbs_now[i]))
    
    # both unhappy - same
    i = i_both_edge
    alpha[i] = gamma*km[i] + (1-gamma)*kf[i]
    #assert np.all(kf[i]<=km[i])
    #assert np.all(np.isinf(nbs_bef[i]))        
    #assert np.all(np.isinf(nbs_now[i]))
    #assert np.all(alpha[i]>0)
    #assert np.all(alpha[i]<1)
    
    # here we need to define few extra objects. vs refers to variable size 
    # so they are not the same size as sm and sf
    # the double indexing below if hard to digest but this is probably the most
    # elegant repersentation of nested if statements and it works
    i = i_fem_edge # just an alias
    vs_sm_hit = ((1-kf[i])*sm_bef[i] + kf[i]*sm_now[i])
    vs_prop = gamma*vs_sm_hit / (vs_sm_hit - sm_now[i]) # 
    vs_i = (vs_prop <= 1)
    alpha[tm(i, vs_i)] = (1-vs_prop[vs_i])*kf[i][vs_i] + vs_prop[vs_i] #alpha[i][vs_i] = ...
    alpha[tm(i,~vs_i)] = 1.0 #alpha[i][~vs_i] = 1.0    
    #assert np.all( np.abs( ((1-kf[i])*sf_bef[i] + kf[i]*sf_now[i]) ) < 1e-5 )
    #assert np.all( alpha[i][vs_i] >= kf[i][vs_i] )
    #assert np.all(np.isinf(nbs_bef[i]))        
    #assert np.all(~np.isinf(nbs_now[i]))
    #assert np.all(alpha[i] > 0)
    
    
    
    i = i_mal_edge  # just an alias
    vs_sf_hit = (1-km[i])*sf_bef[i] + km[i]*sf_now[i]
    vs_prop = gamma - (1-gamma) * sf_bef[i] / (vs_sf_hit - sf_bef[i]) 
    vs_i = (vs_prop >= 0)
    alpha[tm(i, vs_i)] = vs_prop[vs_i]*km[i][vs_i] #alpha[i][vs_i]  = ...
    alpha[tm(i, ~vs_i)] = 0.0 #alpha[i][~vs_i] = 0.0
    alpha[tm(i, vs_i)]  = vs_prop[vs_i]*km[i][vs_i]
    
    #assert np.all(alpha[i] < 1)
    #assert np.all(~np.isinf(nbs_bef[i]))        
    #assert np.all(np.isinf(nbs_now[i]))
    
    # extra checks
    
    #assert np.all( np.abs( ((1-km[i])*sm_bef[i] + km[i]*sm_now[i]) ) < 1e-5 )
    #assert np.all( alpha[i] <= km[i] )
    #assert np.all( (i_no_hope) | (i_both_happy) | (i_both_edge) | (i_fem_edge) | (i_mal_edge))
    #assert np.all(i_no_hope ==  np.isnan(alpha))
    
    
    
    
    i = ~i_no_hope
    i_a_neg = np.full_like(alpha,False,dtype=np.bool)    
    i_a_neg[i] = (alpha[i] <= 0)
    i_a_big = np.full_like(alpha,False,dtype=np.bool)
    i_a_big[i] = (alpha[i] >= 1)
    i_a_good = np.full_like(alpha,False,dtype=np.bool)
    i_a_good[i] =  (alpha[i] > 0) & (alpha[i] < 1)
    i_a_nan = np.isnan(alpha)
    
    
    #assert np.all(~i_a_nan[~i_no_hope])
    
    nbs_mat[i_a_neg] = nbs_bef[i_a_neg]
    assert np.all(~np.isinf(nbs_bef[i_a_neg]))
    nbs_mat[i_a_big] = nbs_now[i_a_big]
    assert np.all(~np.isinf(nbs_now[i_a_big]))
    
    # this can really be optimized we do not need nbs_bef and nbs_aft
    vs_sm_a = alpha[i_a_good]*sm_now[i_a_good] + (1-alpha[i_a_good])*sm_bef[i_a_good]
    vs_sf_a = alpha[i_a_good]*sf_now[i_a_good] + (1-alpha[i_a_good])*sf_bef[i_a_good]
    nbs_mat[i_a_good] = (vs_sf_a**gamma) * (vs_sm_a**(1-gamma))
    
    ws_mat[~i_a_nan] = np.maximum(np.minimum(alpha[~i_a_nan],1.0),0.0)
    
    assert np.all(np.max(nbs_mat,axis=1)>0)
    
    
    
    i_theta = np.argmax(nbs_mat,axis=1)
    inds = np.arange(sf.shape[0])
    
    
    w_theta = ws_mat[inds,i_theta]#np.take_along_axis(ws_mat,i_theta[:,None],1).squeeze() # note that there are no +1
    nbsv = nbs_mat[inds,i_theta]#np.take_along_axis(nbs_mat,i_theta[:,None],1).squeeze()
    
    return i_theta, w_theta, nbsv



@njit#(parallel=True)
def max_nbs_loop(sf,sm,gamma):
    # this aims to maximize Nash Bargaining surplus that is 
    # gamma*log(sf) + (1-gamma)*log(sm) if sf, sm>0
    # this assumes that sf and sm are piecewise linear functions defined on the
    # same grid, therefore it interpolates them, obtains exact mathematical
    # solution each piece of the grid and finds the best out of them
    
    nbsv   = np.empty((sf.shape[0],),dtype=np.float64)
    itheta = np.empty((sf.shape[0],),dtype=np.int32)
    wntheta = np.empty((sf.shape[0],),dtype=np.float64)
    
    
    for ii in range(sf.shape[0]):
        sfi = sf[ii,:]
        smi = sm[ii,:]
        
        
        nbs = np.full(sfi.size,-np.inf,dtype=np.float64)
        ws  = np.full(sfi.size,np.nan,dtype=np.float64)
        assert np.all(np.diff(sfi)>0) # we actually just need single crossing
        assert np.all(np.diff(smi)<0)
        
        assert not np.any(sfi==0), 'exact 0 in surplus?'
        assert not np.any(smi==0), 'exact 0 in surplus?'
        
        # the following code is funky at 0
        assert np.sum( (np.signbit(sfi[1:]) != np.signbit(sfi[:-1])) ) <= 1 # check single crossing
        assert np.sum( (np.signbit(smi[1:]) != np.signbit(smi[:-1])) ) <= 1 # check single crossing
        
        for j in range(1,sfi.size,1):
            sf_now = sfi[j]
            sf_bef = sfi[j-1]
            sm_now = smi[j]
            sm_bef = smi[j-1]
            
            
            dsf = sf_now - sf_bef
            kf = sf_bef / (-dsf)
            neg_dsm = sm_bef - sm_now
            km = sm_bef / (neg_dsm)
            
            nbs_bef = sf_bef**(gamma) * sm_bef**(1-gamma) if (sf_bef > 0 and sm_bef > 0) else -np.inf
            nbs_now = sf_now**(gamma) * sm_now**(1-gamma) if (sf_now > 0 and sm_now > 0) else -np.inf
            
            # four cases 
            
            if sf_now <= 0 or sm_bef <= 0: # no hope
                continue
            elif sf_bef >= 0 and sm_now >= 0:
                assert sf_now >= 0 and sm_bef >= 0
                # lots of agreement
                alpha = gamma*(sm_bef/neg_dsm) - (1-gamma)*(sf_bef/dsf)
                alpha2 = gamma*km + (1-gamma)*kf
                assert np.abs(alpha-alpha2) < 1e-5
            
            elif sf_bef < 0 and sf_now > 0 and sm_now < 0 and sm_bef > 0:
                # edge case
                assert kf<= km # this should be taken care of externally
                alpha = (1-gamma)*kf + gamma*km
            elif sf_bef < 0 and sf_now > 0 and sm_now > 0 and sm_bef > 0:
                # edge case for f
                assert -1e-5 < ((1-kf)*sf_bef + kf*sf_now) < 1e-5
                sm_hit = (1-kf)*sm_bef + kf*sm_now
                prop = gamma*sm_hit / (sm_hit - sm_now)
                alpha = (1-prop)*kf + prop if prop < 1 else 1.0                
                assert alpha>=kf
                 
            elif sf_bef > 0 and sf_now > 0 and sm_now < 0 and sm_bef > 0:
                # edge case for m
                assert -1e-3 < ((1-km)*sm_bef + km*sm_now) < 1e-3
                
                sf_hit = (1-km)*sf_bef + km*sf_now                
                
                assert sf_hit >= sf_bef         
                
                
                prop = gamma - (1-gamma) * sf_bef / (sf_hit - sf_bef)                
                alpha = prop*km if prop > 0 else 0.0    
                assert alpha<=km                
            else:
                print((sf_bef,sf_now,sm_bef,sm_now))
                raise Exception('non-monotonicity or coding error')
                
                
            # we got alpha, so the resolution is    
                
            if alpha <= 0:
                assert ~np.isinf(nbs_bef)
                nbs[j] = nbs_bef
                ws[j] = 0.0
                
            elif alpha >= 1:
                assert ~np.isinf(nbs_now)
                nbs[j] = nbs_now
                ws[j] = 1.0
                
            else:
                # TODO: check this
                sf_a = alpha*sf_now + (1-alpha)*sf_bef
                sm_a = alpha*sm_now + (1-alpha)*sm_bef
                nbs[j] = sf_a**(gamma) * sm_a**(1-gamma) 
                ws[j] = alpha
                assert nbs[j]>=nbs_bef and nbs[j]>=nbs_now
                
            
                
        assert np.any(nbs>0)
        it_best = np.argmax(nbs) 
        
        wntheta[ii] = ws[it_best]
        itheta[ii] = it_best-1 # note that we never write anything in nbs[0]
        nbsv[ii] = nbs[it_best]
    
    return itheta, wntheta, nbsv
    
          