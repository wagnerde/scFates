import numpy as np
import pandas as pd
import igraph
from anndata import AnnData

from copy import deepcopy
from functools import partial
from statsmodels.stats.weightstats import DescrStatsW

import warnings
from .. import logging as logg
from .. import settings

import sys
sys.setrecursionlimit(10000)

def slide_cells(
    adata: AnnData,
    root_milestone,
    milestones,
    win: int = 50,
    mapping: bool = True,
    copy: bool = False,
    ):
    
    adata = adata.copy() if copy else adata
    
    tree = adata.uns["tree"]
    
    mlsc = deepcopy(adata.uns["milestones_colors"])
    mlsc_temp = deepcopy(mlsc)
    dct = dict(zip(adata.obs.milestones.cat.categories.tolist(),
                   np.unique(tree["pp_seg"][["from","to"]].values.flatten().astype(int))))
    keys = np.array(list(dct.keys()))
    vals = np.array(list(dct.values()))

    leaves=list(map(lambda leave: dct[leave],milestones))
    root=dct[root_milestone]
    
    def getsegs(g,root,leave,tree):
        path=np.array(g.vs[:]["name"])[np.array(g.get_shortest_paths(str(root),str(leave)))][0]
        segs = list()
        for i in range(len(path)-1):
            segs= segs + [np.argwhere((tree["pp_seg"][["from","to"]].astype(str).apply(lambda x: 
                                                                                    all(x.values == path[[i,i+1]]),axis=1)).to_numpy())[0][0]]
        segs=tree["pp_seg"].index[segs].tolist()
        return(segs)


    edges=tree["pp_seg"][["from","to"]].astype(str).apply(tuple,axis=1).values
    img = igraph.Graph()
    img.add_vertices(np.unique(tree["pp_seg"][["from","to"]].values.flatten().astype(str)))
    img.add_edges(edges)

    paths = list(map(lambda l: getsegs(img,root,l,tree),leaves))
    
    
    seg_progenies = list(set.intersection(*[set(path) for path in paths]))
    seg_branch1 = list(set.difference(set(paths[0]),set(seg_progenies)))
    seg_branch2 = list(set.difference(set(paths[1]),set(seg_progenies)))
    pp_probs = tree["R"].sum(axis=0)
    pps = tree["pp_info"].PP[tree["pp_info"].seg.isin(np.array(seg_progenies+seg_branch1+seg_branch2).astype(str))].index

    seg_branch1 = [str(seg) for seg in seg_branch1]
    seg_branch2 = [str(seg) for seg in seg_branch2]
    seg_progenies = [str(seg) for seg in seg_progenies]

    def region_extract(pt_cur,segs_cur):
        freq = list()

        pp_next = pps[(tree["pp_info"].loc[pps,"time"].values >= pt_cur) & 
                      tree["pp_info"].loc[pps,"seg"].isin(segs_cur).values]


        cmsm = np.cumsum(pp_probs[pp_next][np.argsort(tree["pp_info"].loc[pp_next,"time"].values)])
        inds=np.argwhere(cmsm > win).flatten()

        if len(inds)==0:
            if (cmsm.max() > win/2):
                if mapping:
                    cell_probs = tree["R"][:,pp_next].sum(axis=1)
                else:
                    cell_probs = np.isin(np.apply_along_axis(lambda x: np.argmax(x),axis=1,arr=tree["R"]),pp_next)*1
                freq = freq+[cell_probs]
            return freq
        else: 
            pps_region = pp_next[np.argsort(tree["pp_info"].loc[pp_next,"time"].values)][:inds[0]]
            if mapping:
                cell_probs = tree["R"][:,pps_region].sum(axis=1)
            else:
                cell_probs = np.isin(np.apply_along_axis(lambda x: np.argmax(x),axis=1,arr=tree["R"]),pps_region)*1

            freq = freq+[cell_probs]
            pt_cur = tree["pp_info"].loc[pps_region,"time"].max()



            if (sum(~tree["pp_info"].loc[pps_region,:].seg.isin(seg_progenies))==0):
                res = region_extract(pt_cur,segs_cur)
                return freq+res

            elif (sum(~tree["pp_info"].loc[pps_region,:].seg.isin(seg_branch1))==0):
                res = region_extract(pt_cur,segs_cur)
                return freq+res

            elif (sum(~tree["pp_info"].loc[pps_region,:].seg.isin(seg_branch2))==0):

                res = region_extract(pt_cur,segs_cur)
                return freq+res


            elif (~(sum(~tree["pp_info"].loc[pps_region,:].seg.isin([str(seg) for seg in seg_progenies]))==0)):
                pt_cur1 = tree["pp_info"].loc[pps_region,"time"][tree["pp_info"].loc[pps_region,"seg"].isin([str(seg) for seg in seg_branch1])].max()
                segs_cur1 = seg_branch1
                pt_cur2 = tree["pp_info"].loc[pps_region,"time"][tree["pp_info"].loc[pps_region,"seg"].isin([str(seg) for seg in seg_branch2])].max()
                segs_cur2 =seg_branch2
                res1 = region_extract(pt_cur1,segs_cur1)
                res2 = region_extract(pt_cur2,segs_cur2)
                return freq+res1+res2
            
    pt_cur = tree["pp_info"].loc[pps,"time"].min()
    segs_cur=np.unique(np.array(seg_progenies+seg_branch1+seg_branch2).flatten().astype(str))
    
    freq=region_extract(pt_cur,segs_cur)
    name=root_milestone+"->"+milestones[0]+"<>"+milestones[1]
    adata.uns["tree"][name+"-cell_freq"]=freq
    
    logg.hint(
        "added \n"
        "    'tree/"+name+"-cell_freq', probability assignment of cells on non intersecting windows (adata.uns)")
    
    return adata if copy else None



def slide_cors(
    adata: AnnData,
    root_milestone,
    milestones,
    copy: bool = False,
    ):
    
    adata = adata.copy() if copy else adata
       
    tree = adata.uns["tree"]    
    
    mlsc = deepcopy(adata.uns["milestones_colors"])
    mlsc_temp = deepcopy(mlsc)
    dct = dict(zip(adata.obs.milestones.cat.categories.tolist(),
                   np.unique(tree["pp_seg"][["from","to"]].values.flatten().astype(int))))
    keys = np.array(list(dct.keys()))
    vals = np.array(list(dct.values()))

    leaves=list(map(lambda leave: dct[leave],milestones))
    root=dct[root_milestone]
    
    name=root_milestone+"->"+milestones[0]+"<>"+milestones[1]
    
    bif = adata.uns["tree"][name]
    freq = adata.uns["tree"][name+"-cell_freq"]
    nwin = len(adata.uns["tree"][name+"-cell_freq"])
    
    genesetA = bif.index[(bif["branch"]==milestones[0]).values & (bif["module"]=="early").values]
    genesetB = bif.index[(bif["branch"]==milestones[1]).values & (bif["module"]=="early").values]
    genesets = np.concatenate([genesetA,genesetB])
    
    def gather_cor(i,geneset):
        freq=adata.uns["tree"][name+"-cell_freq"][i]
        cormat = pd.DataFrame(DescrStatsW(np.array(adata[adata.uns["tree"]["cells_fitted"],genesets].X),weights=freq).corrcoef,
                              index=genesets,columns=genesets)
        np.fill_diagonal(cormat.values, np.nan)
        return cormat.loc[:,geneset].mean(axis=1)

    
    gather = partial(gather_cor, geneset=genesetA)
    corA=pd.concat(list(map(gather,range(nwin))),axis=1)

    gather = partial(gather_cor, geneset=genesetB)
    corB=pd.concat(list(map(gather,range(nwin))),axis=1)
    
    corAB=pd.concat([corA,corB], keys=milestones) 
    corAB.columns=[str(c) for c in corAB.columns]
    
    adata.uns["tree"][name+"-corAB"]=corAB
    
    logg.hint(
        "added \n"
        "    'tree/"+name+"-corAB', gene-gene correlation modules (adata.uns)")
    
    return adata if copy else None



def synchro_path(
    adata: AnnData,
    root_milestone,
    milestones,
    n_map=1,
    n_jobs=None,
    perm=True,
    w=200,
    step=30,
    winp=10,
    copy: bool = False,
    ):
    
    adata = adata.copy() if copy else adata
       
    tree = adata.uns["tree"]    
    
    mlsc = deepcopy(adata.uns["milestones_colors"])
    mlsc_temp = deepcopy(mlsc)
    dct = dict(zip(adata.obs.milestones.cat.categories.tolist(),
                   np.unique(tree["pp_seg"][["from","to"]].values.flatten().astype(int))))
    keys = np.array(list(dct.keys()))
    vals = np.array(list(dct.values()))

    leaves=list(map(lambda leave: dct[leave],milestones))
    root=dct[root_milestone]
    
    name=root_milestone+"->"+milestones[0]+"<>"+milestones[1]
    
    def synchro_map(m):
        df = tree["pseudotime_list"][str(m)]
        edges = tree["pp_seg"][["from","to"]].astype(str).apply(tuple,axis=1).values
        img = igraph.Graph()
        img.add_vertices(np.unique(tree["pp_seg"][["from","to"]].values.flatten().astype(str)))
        img.add_edges(edges)  

        genesetA=adata.uns["tree"][name].index[(adata.uns["tree"][name].module=="early") & 
                                               (adata.uns["tree"][name].branch==milestones[0])]
        genesetB=adata.uns["tree"][name].index[(adata.uns["tree"][name].module=="early") & 
                                               (adata.uns["tree"][name].branch==milestones[1])]

        def synchro_milestone(leave):
            cells=getpath(img,root,tree["tips"],leave,tree,df).index
            mat=pd.DataFrame(adata[cells,adata.uns["tree"][name].index[adata.uns["tree"][name].module=="early"]].X,
                        index=cells,columns=adata.uns["tree"][name].index[adata.uns["tree"][name].module=="early"])
            mat=mat.iloc[adata.obs.t[mat.index].argsort().values,:]

            if permut==True:
                winperm=np.min([winp,mat.shape[0]])
                for i in np.arange(0,mat.shape[0]-winperm,winperm):
                    mat.iloc[i:(i+winp),:]=mat.iloc[i:(i+winp),np.random.permutation(mat.shape[1])].values

            def slide_path(i):
                cls=mat.index[i:(i+w)]
                cor=mat.loc[cls,:].corr(method="spearman")
                np.fill_diagonal(cor.values, np.nan)
                corA=cor.loc[:,genesetA].mean(axis=1)
                corB=cor.loc[:,genesetB].mean(axis=1)
                corA[genesetA] = (corA[genesetA] - 1/len(genesetA))*len(genesetA)/(len(genesetA)-1)
                corB[genesetB] = (corB[genesetB] - 1/len(genesetB))*len(genesetB)/(len(genesetB)-1)

                return pd.Series({"t":adata.obs.t[cls].mean(),
                             "dist":(corA[genesetA].mean()-corA[genesetB].mean())**2+(corB[genesetA].mean()-corB[genesetB].mean())**2,
                             "corAA":corA[genesetA].mean(),"corBB":corB[genesetB].mean(),"corAB":corA[genesetB].mean(),
                                 "n_map":m})


            return pd.concat(list(map(slide_path,np.arange(0,mat.shape[0]-w,step))),axis=1).T

        return pd.concat(list(map(synchro_milestone,leaves)),keys=milestones)
    
    
    if n_map>1:
        permut = False
        stats = Parallel(n_jobs=n_jobs)(delayed(synchro_map)(i) for i in tqdm(range(n_map)))
        allcor_r = pd.concat(stat)
        if perm:
            permut=True
            stats = Parallel(n_jobs=n_jobs)(delayed(synchro_map)(i) for i in tqdm(range(n_map)))
            allcor_p=pd.concat(stats)
            allcor=pd.concat([allcor_r,allcor_p],keys=["real","permuted"])
        else:
            allcor=pd.concat([allcor_r], keys=['real'])
    else:
        permut=False
        allcor_r=pd.concat(list(map(synchro_map,range(n_map))))

        if perm:
            permut=True
            allcor_p=pd.concat(list(map(synchro_map,range(n_map))))
            allcor=pd.concat([allcor_r,allcor_p],keys=["real","permuted"])
        else:
            allcor=pd.concat([allcor_r], keys=['real'])
    
    adata.uns["tree"][name+"-synchro"]=allcor
    
    adata.uns["milestones_colors"]=mlsc_temp
    
    logg.hint(
        "added \n"
        "    'tree/"+name+"-synchro', mean local gene-gene correlations of all possible gene pairs inside one module, or between the two modules (adata.uns)")
    
    return adata if copy else None


def getpath(g,root,tips,tip,tree,df):
    warnings.filterwarnings("ignore")
    try:
        path=np.array(g.vs[:]["name"])[np.array(g.get_shortest_paths(str(root),str(tip)))][0]
        segs = list()
        for i in range(len(path)-1):
            segs= segs + [np.argwhere((tree["pp_seg"][["from","to"]].astype(str).apply(lambda x: 
                                                                                    all(x.values == path[[i,i+1]]),axis=1)).to_numpy())[0][0]]
        segs=tree["pp_seg"].index[segs]
        pth=df.loc[df.seg.astype(int).isin(segs),:].copy(deep=True)
        pth["branch"]=str(root)+"_"+str(tip)
        warnings.filterwarnings("default")
        return(pth)
    except IndexError:
        pass