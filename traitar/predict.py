#!/usr/bin/env python
import os.path
import pandas as ps
import sys
from traitar.PhenotypeCollection import PhenotypeCollection

"""predict new samples"""

def filter_pred(scores, is_majority, k):
    """either do majority vote aggregation or conservative all or nothing vote"""
    if is_majority:
        if (scores > 0).sum() >= (k/2 + 1):
            return scores[scores >= 0].mean()
        else:
            return ps.np.NaN
    else:
        if (scores > 0).all():
            return scores.mean()
        else:
            return ps.np.NaN

def aggregate(pred_df, k, out_dir, pt2acc):
    """employ different prediction strategies"""
    out = ["majority-vote", "conservative-vote", "single-votes"]
    maj_pred_dfs = ps.DataFrame(ps.np.zeros(shape = (pred_df.shape[0], pred_df.shape[1] / k)), columns = ["%s" % i for i in range(pred_df.shape[1]/k)])
    maj_pred_dfs.index = pred_df.index
    maj_pred_dfs_columns = maj_pred_dfs.columns.tolist()
    for i in range(pred_df.shape[1] / k):
        maj_pred_dfs_columns[i] = pred_df.columns.values[i * k].split("_")[0] 
        maj_pred_dfs.iloc[:, i] = pred_df.iloc[:, (i * k) : (i * k + k)].apply(lambda x: (x > 0).sum(), axis = 1).astype('int')
    maj_pred_dfs.columns = pt2acc.loc[maj_pred_dfs_columns, :].iloc[:, 0]
    #majority vote
    maj_pred_dfs.to_csv("%s/predictions_%s.txt"%(out_dir, out[2]), sep = "\t", float_format='%.0f', encoding = "utf-8")
    (maj_pred_dfs >= k/2 + 1).astype('int').to_csv("%s/predictions_%s.txt"%(out_dir, out[0]), sep = "\t", float_format='%.0f', encoding = "utf-8")
    (maj_pred_dfs == k).astype('int').to_csv("%s/predictions_%s.txt"%(out_dir, out[1]), sep = "\t", float_format='%.0f', encoding = "utf-8")   #conservative vote
    return maj_pred_dfs
    

    
def majority_predict(pt, pt_models, test_data, k, bias_weight = 1):
    """predict the class label based on a committee vote of the models in models""" 
    #TODO if the classification model is trained on non binary data we would require the same normalization applied to the training data 
    #binarize
    test_data_n = (test_data > 0).astype('int')
    #check if classification model exists for the requested phenotype
    try: 
        bias = pt_models.get_bias(pt)
        predictors = pt_models.get_predictors(pt)
    except KeyError:
        return ps.DataFrame()
    #build prediction matrix with the k best models
    preds = ps.np.zeros((test_data.shape[0], k))
    for i in range(k):
        preds[:, i] = bias.iloc[i, 0] * bias_weight +  predictors.iloc[:, i].dot(test_data_n.loc[:, predictors.iloc[:, i].index].T)
        pred_df = ps.DataFrame(preds, index = test_data.index)
    #set column names
    pred_df.columns = ["%s_%s" %(pt, predictors.columns[i].split("_")[0]) for i in range(k)]
    return pred_df

def annotate_and_predict(pt_models, summary_f, out_dir, k):
    """load annotation previously generated with HMMER and predict phenotypes with phypat and phypat+GGL models"""
    pred_df = ps.DataFrame()
    #read pfam to description file
    pfam_mapping = pt_models.get_pf2desc()
    pt_mapping = pt_models.get_pt2acc()
    #read annotation file
    m = ps.read_csv(summary_f, sep="\t", index_col = 0)
    #restrict to those pfams contained in the model
    #m_red = m.loc[:, pfam_mapping.index ].astype('int')
    #m.columns = pfam_mapping.index
    for pt in pt_mapping.index:
        #predict an append to prediction df
        preds = majority_predict(pt, pt_models, m, k)
        pred_df = ps.concat([pred_df, preds], axis = 1)
    pred_df.index = m.index
    pred_df.to_csv("%s/predictions_raw.txt"%out_dir, sep = "\t", float_format='%.3f')
    #aggregate predictions
    aggr_dfs = aggregate(pred_df, k, out_dir, pt_mapping)
    return pred_df


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser("predict phenotypes from hmmer Pfam annotation")
    parser.add_argument("pt_models", help='archive with the phenotype predictors')
    parser.add_argument("out_dir", help='directory for the phenotype predictions')
    #parser.add_argument("phenotype_f", help='file with ids of phenotypes that should be predicted')
    parser.add_argument("annotation_matrix", help='summary file with pfams')
    parser.add_argument("-k", "--voters", default = 5, help='use this number of voters for the classification', type = int)
    args = parser.parse_args()
    pt_models = PhenotypeCollection(args.pt_models)
    annotate_and_predict(pt_models, args.annotation_matrix,  args.out_dir, args.voters) 
