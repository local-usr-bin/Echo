"""Explicit interpolation definitions; no physics or pressure rescaling."""
import time
import numpy as np

METHODS=("nearest","linear_complex","linear_magnitude","cosine_complex","cosine_magnitude")


def cosine_transform(n):
    index=np.arange(n+1)
    w=np.ones(n+1);w[[0,-1]]=.5
    return (2/n)*w[:,None]*np.cos(np.pi*np.outer(index,index)/n)*w[None,:]


def fit(method,axes,pressure):
    values=np.abs(pressure) if method.endswith("magnitude") else pressure
    obj={"method":method,"axes":axes,"values":values}
    if method.startswith("cosine"):
        transform=cosine_transform(len(axes[0])-1)
        obj["coefficients"]=transform@values
        if len(axes)==2:
            obj["coefficients"]=obj["coefficients"]@cosine_transform(len(axes[1])-1).T
    obj["model_array_bytes"]=int(sum(x.nbytes for x in axes)+values.nbytes+obj.get("coefficients",np.empty(0)).nbytes)
    return obj


def predict(model,coordinates):
    method=model["method"];axes=model["axes"];values=model["values"]
    q=np.asarray(coordinates)
    if method.startswith("cosine"):
        basis=[np.cos(np.outer(q[:,i]/axis[-1],np.arange(len(axis)))*np.pi) for i,axis in enumerate(axes)]
        intermediate=basis[0]@model["coefficients"]
        result=(intermediate if len(axes)==1 else np.einsum("ij,ij->i",intermediate,basis[1]))
        working=sum(b.nbytes for b in basis)+intermediate.nbytes+result.nbytes
    elif method=="nearest":
        indices=[np.clip(np.floor(q[:,i]/(axis[1]-axis[0])+.5).astype(int),0,len(axis)-1) for i,axis in enumerate(axes)]
        result=values[tuple(indices)]
        working=sum(ix.nbytes for ix in indices)+result.nbytes
    else:
        lower=[];fraction=[]
        for i,axis in enumerate(axes):
            normalized=q[:,i]/(axis[1]-axis[0])
            ix=np.clip(np.floor(normalized).astype(int),0,len(axis)-2)
            lower.append(ix);fraction.append(normalized-ix)
        ix=lower[0];t=fraction[0]
        if len(axes)==1:
            result=(1-t)*values[ix]+t*values[ix+1]
        else:
            iy=lower[1];u=fraction[1]
            result=((1-t)*(1-u)*values[ix,iy]+t*(1-u)*values[ix+1,iy]
                    +(1-t)*u*values[ix,iy+1]+t*u*values[ix+1,iy+1])
        working=sum(a.nbytes for a in lower+fraction)+result.nbytes
    return result,int(working)


def timed_fit(method,axes,pressure):
    times=[]
    for _ in range(3):
        t=time.perf_counter();model=fit(method,axes,pressure);times.append(time.perf_counter()-t)
    return model,float(np.median(times))


def timed_predict(model,coordinates):
    times=[]
    for _ in range(3):
        t=time.perf_counter();values,working=predict(model,coordinates);times.append(time.perf_counter()-t)
    return values,float(np.median(times)),working


def validate_algebra():
    x=np.linspace(0,5,21);y=np.linspace(0,4,17)
    qx=5*(np.arange(73)+.37)/73;qy=4*(np.arange(73)+.61)/73
    records=[]
    for method in METHODS:
        for dim in (1,2):
            axes=[x] if dim==1 else [x,y]
            p=np.full(tuple(len(v) for v in axes),1.2-.7j)
            value,_=predict(fit(method,axes,p),np.column_stack((qx,)) if dim==1 else np.column_stack((qx,qy)))
            expected=abs(1.2-.7j) if method.endswith("magnitude") else 1.2-.7j
            records.append({"method":method,"test":"complex_constant","dimension":dim,"max_absolute_error":float(np.max(abs(value-expected)))})
    function=lambda x,y:(.8+.2j)*np.cos(3*np.pi*x/5)*np.cos(2*np.pi*y/4)+(-.1+.5j)*np.cos(7*np.pi*x/5)*np.cos(4*np.pi*y/4)
    xx,yy=np.meshgrid(x,y,indexing="ij")
    prediction,_=predict(fit("cosine_complex",[x,y],function(xx,yy)),np.column_stack((qx,qy)))
    records.append({"method":"cosine_complex","test":"known_mixed_complex_cosine_off_grid","dimension":2,
                    "max_absolute_error":float(np.max(abs(prediction-function(qx,qy))))})
    polynomial=lambda x,y:(.2+.5j)+(.3-.1j)*x+(.4+.3j)*y+(.02-.03j)*x*y
    prediction,_=predict(fit("linear_complex",[x,y],polynomial(xx,yy)),np.column_stack((qx,qy)))
    records.append({"method":"linear_complex","test":"known_complex_bilinear_off_grid","dimension":2,
                    "max_absolute_error":float(np.max(abs(prediction-polynomial(qx,qy))))})
    assert max(r["max_absolute_error"] for r in records)<1e-12,records
    return records
