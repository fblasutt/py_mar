#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Sep 26 20:44:26 2019

@author: egorkozlov
"""

import numpy as np
from numba import jit, prange, cuda, float32


from platform import system

#from numba.pycc import CC

#cc = CC('aot_test')

@jit('float64[:](float64[:], int64, float64, float64)',nopython=True)
#@cc.export('build_s_grid','float64[:](float64[:], int64, float64, float64)')
def build_s_grid(agrid,n_between,da_min,da_max):
    sgrid = np.array([0.0],np.float64)
    for j in range(agrid.size-1):
        step = (agrid[j+1] - agrid[j])/n_between
        if step >= da_min and step <= da_max:
            s_add = np.linspace(agrid[j],agrid[j+1],n_between)[:-1]
        elif step < da_min:
            s_add = np.arange(agrid[j],agrid[j+1],da_min)
        elif step > da_max:
            s_add = np.arange(agrid[j],agrid[j+1],da_max)
        sgrid = np.concatenate((sgrid,s_add))
    
    sgrid = np.concatenate((sgrid,np.array([agrid[-1]])))
            
    if sgrid[0] == sgrid[1]: 
        sgrid = sgrid[1:]
        
    return sgrid


@jit('Tuple((int32[:],float32[:]))(float64[:],float64[:])',nopython=True)
#@cc.export('sgrid_on_agrid','Tuple((int32[:],float32[:]))(float64[:],float64[:])')
def sgrid_on_agrid(sgrid,agrid):
    
    
    ind = np.empty(sgrid.size,dtype=np.int32)
    p = np.empty(sgrid.size,dtype=np.float32)
    # this uses the fact that both agrid and sgrid are sorted
    # this returns indices and weights that are needed for interpolation of 
    # something that is defined on agrid for values of sgrid
    
    # sgrid[i] = p[i]*agrid[ind[i]] + (1-p[i])*agrid[ind[i]+1]
    
    na = agrid.size
    
    i_next_a = 1
    a_next, a_this = agrid[1], agrid[0]
    
    for i in range(sgrid.size):
        s_this = sgrid[i]
        while a_next < s_this and i_next_a < na-1:
            a_this = agrid[i_next_a]
            i_next_a += 1
            a_next = agrid[i_next_a]
    
        
        #assert s_this >= a_this
        
        ind[i] = i_next_a - 1        
        p[i] = (a_next - s_this)/(a_next - a_this)
        
    
       
    return ind, p
      
#@jit('float32[:](int32[:],float32[:],float32[:])',nopython=True)
def get_EV(ind,p,EVin):
    #EVout = np.empty(ind.shape,np.float32)
    #EVout[:] = p*EVin[ind] + (1-p)*EVin[ind+1]
    print('this is deprecated')    
    return get_EVM(ind,p,EVin)

#@jit('float32[:](int32[:],float32[:],float32[:])',nopython=True)
def get_EVM(ind,p,EVin):
    
    ev_aux_shape  = EVin.shape[1:]
    shap = (ind.size,) + ev_aux_shape
    EVout = np.empty(shap,np.float32)
    
    pb = p.reshape(((p.size,)+(1,)*len(ev_aux_shape)))
    EVout[:] = pb*EVin[ind,...] + (1-pb)*EVin[ind+1,...]    
    return EVout



@jit(nopython=True,parallel=True)
def v_optimize_cpu_loop(money,sgrid,EV_on_sgrid,sigma,beta):
    
    V, c, s = np.empty(money.shape,np.float64), np.empty(money.shape,np.float64), np.empty(money.shape,np.float64)
    
    i_sav = 1
    ns = sgrid.size
    
    oms = 1-sigma
    
    # does not allow for logs yet
    def u(c): return (c**(oms))/(oms)    
    
    for im in range(money.size): # or prange
        mi = money[im]        
        c_best = mi
        V_best = np.float32(-np.inf)
        s_best = np.float32(0.0)   
        
        for i_sav in range(ns):
            s_current = sgrid[i_sav]
            c_current = mi - s_current
            if c_current <= 0: break                 
            V_new = u(c_current) + beta*EV_on_sgrid[i_sav]
            
            # update if imporved
            if V_new >= V_best:
                c_best = c_current
                V_best = V_new
                s_best = s_current
                    
            
        c[im] = c_best
        s[im] = s_best
        V[im] = V_best
        
    return V, c, s



@jit(nopython=True)#,parallel=True)
def v_optimize_cpu_a(money,sgrid,EV_on_sgrid,sigma,beta):
    
    V, c, s = np.empty(money.shape,np.float64), np.empty(money.shape,np.float64), np.empty(money.shape,np.float64)
    
    i_sav = 1
    ns = sgrid.size
    
    oms = 1-sigma
    
    # does not allow for logs yet
    def u(c): return (c**(oms))/(oms)    
    
    for im in range(money.size): # or prange
        #i_sav = 1 # use this if parallel
        mi = money[im]
        while i_sav < ns-1 and mi > sgrid[i_sav+1]: i_sav += 1
        
        c_vec = mi - sgrid[:(i_sav+1)]
        V_vec = u(c_vec) + beta*EV_on_sgrid[:(i_sav+1)]
        i_opt = V_vec.argmax()
        c[im] = c_vec[i_opt]
        s[im] = sgrid[i_opt]
        V[im] = V_vec[i_opt]
        
        
        
    return V, c, s


#@jit(nopython=True)

def v_optimize_np(money,sgrid,EV_on_sgrid,sigma,beta):
    
    V, c, s = np.empty(money.size,np.float64), np.empty(money.size,np.float64), np.empty(money.size,np.float64)
    
    
    assert money.ndim == 1
    
    
    oms = 1-sigma
    
    # does not allow for logs yet
    def u(c): return (c**(oms))/(oms)
    
    
    c_mat = np.expand_dims(money,1) - np.expand_dims(sgrid,0)
    u_mat = np.full_like(c_mat,-np.inf)
    u_mat[c_mat>0] = u(c_mat[c_mat>0])
    V_mat = u_mat + beta*np.expand_dims(EV_on_sgrid,0)
    
    i_opt = V_mat.argmax(axis=1)    
    s = sgrid[i_opt]
    c = money - s
    V = u(c) + beta*EV_on_sgrid[i_opt]
    
    return V, c, s



if system() != 'Darwin': import cupy as cp

def v_optimize_cp(money,sgrid,EV_on_sgrid,sigma,beta):
    
    (money,sgrid,EV_on_sgrid) = (cp.asarray(x) for x in  (money,sgrid,EV_on_sgrid))

    V, c, s = cp.empty(money.size,cp.float64), cp.empty(money.size,cp.float64), cp.empty(money.size,cp.float64)
    
    
    assert money.ndim == 1
    
    
    oms = 1-sigma
    
    # does not allow for logs yet
    def u(c): return (c**(oms))/(oms)
    
    c_mat = cp.expand_dims(money,1) - cp.expand_dims(sgrid,0)
    u_mat = cp.full(c_mat.shape,-cp.inf)
    u_mat[c_mat>0] = u(c_mat[c_mat>0])
    V_mat = u_mat + beta*cp.expand_dims(EV_on_sgrid,0)
    
    i_opt = V_mat.argmax(axis=1)    
    s = sgrid[i_opt]
    c = money - s
    V = u(c) + beta*EV_on_sgrid[i_opt] 
    
    return cp.asnumpy(V), cp.asnumpy(c), cp.asnumpy(s)


def v_optimize_gpu(money,sgrid,EV_on_sgrid,sigma,beta):
    
    V, c, s = cuda.device_array(money.shape,np.float64), cuda.device_array(money.shape,np.float64), cuda.device_array(money.shape,np.float64)
    
    ns = sgrid.size    
    oms = 1-sigma        
    money = np.float32(money)
    
    
    bEV_on_sgrid = beta*EV_on_sgrid
    (money,sgrid,bEV_on_sgrid) = (cuda.to_device(np.ascontiguousarray(x)) for x in (money,sgrid,bEV_on_sgrid))
    
    @cuda.jit
    def cuda_ker(money,sgrid,bEV_on_sgrid,c,s,V):
        im = cuda.grid(1)
        nm = money.size
        
        
        def u(c): # scalar
            return (c**(oms))/(oms)
            
        if im < nm:
            mi = money[im]
            #i_sav = 1
            
            c_best = mi
            V_best = np.float32(-np.inf)
            s_best = np.float32(0.0)           
            
            # just another loop
            for i_sav in range(ns):
                s_current = sgrid[i_sav]
                c_current = mi - s_current
                if c_current <= 0: break                 
                V_new = u(c_current) + bEV_on_sgrid[i_sav]
                
                # update if imporved
                if V_new >= V_best:
                    c_best = c_current
                    V_best = V_new
                    s_best = s_current
                    
            
            c[im] = c_best
            s[im] = s_best
            V[im] = V_best
        
    # actually the most important thing is block sizes here
    cuda_ker[money.size,money.size](money,sgrid,bEV_on_sgrid,c,s,V)
    
        
    return V, c, s



def v_optimize_MEV_np(money,sgrid,EV_on_sgrid_M,sigma,beta):
    
    ntheta = EV_on_sgrid_M.shape[-1]
    shp = (money.size,ntheta)
    V, c, s = np.empty(shp,np.float32), np.empty(shp,np.float32), np.empty(shp,np.float32)    
    
    
    oms = 1-sigma
    
    def u(c): return (c**(oms))/(oms)   
    
    
    c_mat = np.expand_dims(money,1) - np.expand_dims(sgrid,0)
    u_mat = np.full(c_mat.shape,-np.inf)
    u_mat[c_mat>0] = u(c_mat[c_mat>0])
    
    V_arr = np.expand_dims(u_mat,2) + beta*np.expand_dims(EV_on_sgrid_M,0)
    
    i_opt = V_arr.argmax(axis=1)
    
    s = sgrid[i_opt]
    c = np.expand_dims(money,1) - s
    V = u(c) + beta*np.take_along_axis(EV_on_sgrid_M,i_opt,0)
    
    return V, c, s


from aux_routines import cp_take_along_axis
def v_optimize_MEV_cp(money,sgrid,EV_on_sgrid_M,sigma,beta):
    
    money,sgrid,EV_on_sgrid_M = (cp.asarray(x) for x in (money,sgrid,EV_on_sgrid_M))
    
    ntheta = EV_on_sgrid_M.shape[-1]
    shp = (money.size,ntheta)
    V, c, s = cp.empty(shp,cp.float32), cp.empty(shp,cp.float32), cp.empty(shp,cp.float32)    
    
    
    oms = 1-sigma
    
    def u(c): return (c**(oms))/(oms)   
    
    
    c_mat = cp.expand_dims(money,1) - cp.expand_dims(sgrid,0)
    u_mat = cp.full(c_mat.shape,-cp.inf)
    u_mat[c_mat>0] = u(c_mat[c_mat>0])
    
    V_arr = cp.expand_dims(u_mat,2) + beta*cp.expand_dims(EV_on_sgrid_M,0)
    
    i_opt = V_arr.argmax(axis=1)
    
    s = sgrid[i_opt]
    c = cp.expand_dims(money,1) - s
    V = u(c) + beta*cp_take_along_axis(EV_on_sgrid_M,i_opt,0)
    
    
    
    return cp.asnumpy(V), cp.asnumpy(c), cp.asnumpy(s)


def v_optimize_MEV_np_massive(money,sgrid,EVM,sigma,beta):
    
    ntheta = EVM.shape[-1]
    shp = money.shape + (ntheta,) # shape of the result
    
    V, c, s = np.empty(shp,np.float32), np.empty(shp,np.float32), np.empty(shp,np.float32)    
    
    oms = 1-sigma
    
    def u(c): return (c**(oms))/(oms)   
    
    ns = sgrid.size
    
    s_expanded = sgrid.reshape((1,ns,1))
    
    c_mat = np.expand_dims(money,1) - s_expanded 
    u_mat = np.full(c_mat.shape,-np.inf)
    u_mat[c_mat>0] = u(c_mat[c_mat>0])
    
    V_arr = np.expand_dims(u_mat,3) + beta*np.expand_dims(EVM,0)
    
    i_opt = V_arr.argmax(axis=1)
    
    s = sgrid[i_opt]
    c = np.expand_dims(money,2) - s
    V = u(c) + beta*np.take_along_axis(EVM,i_opt,0)
    
    return V, c, s


def v_optimize_MEV_cp_massive(money,sgrid,EVM,sigma,beta):
    
    
    money,sgrid,EVM = (cp.asarray(x) for x in (money,sgrid,EVM))
    
    ntheta = EVM.shape[-1]
    shp = money.shape + (ntheta,) # shape of the result
    
    V, c, s = cp.empty(shp,cp.float32), cp.empty(shp,cp.float32), cp.empty(shp,cp.float32)    
    
    oms = 1-sigma
    
    def u(c): return (c**(oms))/(oms)   
    
    ns = sgrid.size
    
    s_expanded = sgrid.reshape((1,ns,1))
    
    c_mat = cp.expand_dims(money,1) - s_expanded 
    u_mat = cp.full(c_mat.shape,-cp.inf)
    u_mat[c_mat>0] = u(c_mat[c_mat>0])
    
    V_arr = cp.expand_dims(u_mat,3) + beta*cp.expand_dims(EVM,0)
    
    i_opt = V_arr.argmax(axis=1)
    
    s = sgrid[i_opt]
    c = cp.expand_dims(money,2) - s
    V = u(c) + beta*cp_take_along_axis(EVM,i_opt,0)
    
    return cp.asnumpy(V), cp.asnumpy(c), cp.asnumpy(s)






signature = 'Tuple((float32[:,:],float32[:,:],float32[:,:]))(float32[:],float32[:],float32[:,:],float32,float32)'
@jit(signature,nopython=True)#,parallel=True)
#@cc.export('vopt_MEV',signature)
def v_optimize_multiEV(money,sgrid,EV_on_sgrid_M,sigma,beta):
    
    ntheta = EV_on_sgrid_M.shape[-1]
    shp = (money.size,ntheta)
    V, c, s = np.empty(shp,np.float32), np.empty(shp,np.float32), np.empty(shp,np.float32)    
    i_sav = 1
    ns = sgrid.size
    
    oms = 1-sigma
    
    def u(c): return (c**(oms))/(oms)
    
    
    for im in range(money.size): # or prange
        #i_sav = 1 # use this if parallel
        mi = money[im]
        while i_sav < ns-1 and mi > sgrid[i_sav+1]: i_sav += 1
        
        c_vec = np.empty(i_sav)        
        c_vec = mi - sgrid[:(i_sav+1)]        
        uv = u(c_vec)
        
        i_opt = np.empty(ntheta,np.int32)
        V_opt = np.empty(ntheta,np.float32)
        
        for it in prange(ntheta):            
            Vvec_it = uv + beta*EV_on_sgrid_M[:(i_sav+1),it]
            iopt = np.argmax(Vvec_it)
            i_opt[it] = iopt
            V_opt[it] = Vvec_it[iopt]
            
            
        
        c[im,:] = c_vec[i_opt]
        s[im,:] = sgrid[i_opt]
        
        V[im,:] = V_opt
        
    return V, c, s


if __name__ == "__main__":
    #cc.compile()  
    
    #from aot_test import build_s_grid, sgrid_on_agrid
    agrid = np.array([0,1,2,4,5,7,10,12,15,20],dtype=np.float64)       

    sgrid = build_s_grid(agrid,10,0.0001,0.1)
    ind, p = sgrid_on_agrid(sgrid,agrid)
    assert np.max(np.abs(p*agrid[ind] + (1-p)*agrid[ind+1]-sgrid)<1e-5)

    EV = np.float32( 8*np.log(1+agrid) )
    
    EV_on_sgrid = get_EV(ind,p,EV)
    
    money = np.linspace(0.4,30,num=100)
    #umult = 1.0
    #uadd  = 0.0
    sigma = 2
    beta = 1.0
    
    #V, c, s = v_optimize(money,sgrid,EV_on_sgrid,umult,sigma,beta,uadd)


    
    