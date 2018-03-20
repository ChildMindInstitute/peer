import os
import csv
import numpy as np
import pandas as pd
import nibabel as nib
from sklearn.svm import SVR
from datetime import datetime
import matplotlib.pyplot as plt
from scipy.stats import ttest_rel
from scipy.stats import pearsonr
from aux_process import *

monitor_width = 1680
monitor_height = 1050

# #############################################################################
# Update subject parameters sheet with new participants

data_path = '/data2/Projects/Jake/Human_Brain_Mapping/'
qap_path_RU = '/data2/HBNcore/CMI_HBN_Data/MRI/RU/QAP/qap_functional_temporal.csv'
qap_path_CBIC = '/data2/HBNcore/CMI_HBN_Data/MRI/CBIC/QAP/qap_functional_temporal.csv'
output_path = '/home/json/Desktop/peer/Figures'

params = pd.read_csv('subj_params.csv', index_col='subject', dtype=object)
sub_ref = params.index.values.tolist()

qap = pd.read_csv(qap_path_RU, dtype=object)
qap['Participant'] = qap['Participant'].str.replace('_', '-')

x_b = 12; x_e = 40; y_b = 35; y_e = 50; z_b = 2; z_e = 13

subj_list = []

with open('peer_didactics.csv', 'a') as updated_params:
    writer = csv.writer(updated_params)

    for subject in os.listdir(data_path):
        if any(subject in x for x in sub_ref) and 'txt' not in subject:
            print(subject + ' is already in subj_params.csv')
        elif 'txt' not in subject:
            writer.writerow([subject])
            print('New participant ' + subject + ' was added')
            subj_list.append(subject)

# #############################################################################
# Import data


def standard_peer(subject_list, gsr=True, update=False):

    for name in subject_list:

        try:

            print('Beginning analysis on participant ' + name)

            training1 = nib.load(data_path + name + '/PEER1_resampled.nii.gz')
            training1_data = training1.get_data()
            testing = nib.load(data_path + name + '/PEER2_resampled.nii.gz')
            testing_data = testing.get_data()

            try:

                training2 = nib.load(data_path + name + '/PEER3_resampled.nii.gz')
                training2_data = training2.get_data()
                scan_count = 3

            except:

                scan_count = 2

            # #############################################################################
            # Global Signal Regression

            print('starting gsr')

            if gsr:

                print('entered loop')

                if scan_count == 2:

                    print('count = 2')

                    training1_data = gs_regress(training1_data)
                    testing_data = gs_regress(testing_data)

                elif scan_count == 3:

                    print('count = 3')

                    training1_data = gs_regress(training1_data, xb, xe, yb, ye, zb, ze)
                    training2_data = gs_regress(training2_data, xb, xe, yb, ye, zb, ze)
                    testing_data = gs_regress(testing_data, xb, xe, yb, ye, zb, ze)

            # #############################################################################
            # Vectorize data into single np array

            listed1 = []
            listed2 = []
            listed_testing = []

            print('beginning vectors')

            for tr in range(int(training1_data.shape[3])):

                tr_data1 = training1_data[xb:xe, yb:ye, zb:ze, tr]
                vectorized1 = np.array(tr_data1.ravel())
                listed1.append(vectorized1)

                if scan_count == 3:

                    tr_data2 = training2_data[xb:xe, yb:ye, zb:ze, tr]
                    vectorized2 = np.array(tr_data2.ravel())
                    listed2.append(vectorized2)

                te_data = testing_data[xb:xe, yb:ye, zb:ze, tr]
                vectorized_testing = np.array(te_data.ravel())
                listed_testing.append(vectorized_testing)

            train_vectors1 = np.asarray(listed1)
            test_vectors = np.asarray(listed_testing)

            if scan_count == 3:
                train_vectors2 = np.asarray(listed2)

            elif scan_count == 2:
                train_vectors2 = []

            # #############################################################################
            # Averaging training signal

            print('average vectors')

            train_vectors = data_processing(scan_count, train_vectors1, train_vectors2)

            # #############################################################################
            # Import coordinates for fixations

            print('importing fixations')

            fixations = pd.read_csv('stim_vals.csv')
            x_targets = np.tile(np.repeat(np.array(fixations['pos_x']), 1)*monitor_width/2, scan_count-1)
            y_targets = np.tile(np.repeat(np.array(fixations['pos_y']), 1)*monitor_height/2, scan_count-1)

            # #############################################################################
            # Create SVR Model

            predicted_x, predicted_y = create_model(train_vectors, test_vectors, x_targets, y_targets)

            # #############################################################################
            # Plot SVR predictions against targets

            # scatter_plot(name, x_targets, y_targets, predicted_x, predicted_y, plot=True, save=False)
            axis_plot(fixations, predicted_x, predicted_y, subj)

            print('Completed participant ' + name)

            # ###############################################################################
            # Get error measurements

            x_res = []
            y_res = []

            for num in range(27):

                nums = num * 5

                for values in range(5):

                    error_x = (abs(x_targets[num] - predicted_x[nums + values]))**2
                    error_y = (abs(y_targets[num] - predicted_y[nums + values]))**2
                    x_res.append(error_x)
                    y_res.append(error_y)

            x_error = np.sqrt(np.sum(np.array(x_res))/135)
            y_error = np.sqrt(np.sum(np.array(y_res))/135)

            params.loc[name, 'x_error_gsr'] = x_error
            params.loc[name, 'y_error_gsr'] = y_error
            params.loc[name, 'scan_count'] = scan_count

            if update:
                params.to_csv('subj_params.csv')

            if scan_count == 3:

                try:

                    fd1 = float(qap[qap['Participant'] == name][qap['Series'] == 'func_peer_run_1']['RMSD (Mean)'])
                    fd2 = float(qap[qap['Participant'] == name][qap['Series'] == 'func_peer_run_2']['RMSD (Mean)'])
                    fd3 = float(qap[qap['Participant'] == name][qap['Series'] == 'func_peer_run_3']['RMSD (Mean)'])
                    dv1 = float(qap[qap['Participant'] == name][qap['Series'] == 'func_peer_run_1']['Std. DVARS (Mean)'])
                    dv2 = float(qap[qap['Participant'] == name][qap['Series'] == 'func_peer_run_2']['Std. DVARS (Mean)'])
                    dv3 = float(qap[qap['Participant'] == name][qap['Series'] == 'func_peer_run_3']['Std. DVARS (Mean)'])

                    fd_score = np.average([fd1, fd2, fd3])
                    dvars_score = np.average([dv1, dv2, dv3])
                    params.loc[name, 'mean_fd'] = fd_score
                    params.loc[name, 'dvars'] = dvars_score

                except:

                    print('Participant not found in QAP')

            elif scan_count == 2:

                try:

                    fd1 = float(qap[qap['Participant'] == name][qap['Series'] == 'func_peer_run_1']['RMSD (Mean)'])
                    fd2 = float(qap[qap['Participant'] == name][qap['Series'] == 'func_peer_run_2']['RMSD (Mean)'])
                    dv1 = float(qap[qap['Participant'] == name][qap['Series'] == 'func_peer_run_1']['Std. DVARS (Mean)'])
                    dv2 = float(qap[qap['Participant'] == name][qap['Series'] == 'func_peer_run_2']['Std. DVARS (Mean)'])

                    fd_score = np.average([[fd1, fd2]])
                    dvars_score = np.average([dv1, dv2])
                    params.loc[name, 'mean_fd'] = fd_score
                    params.loc[name, 'dvars'] = dvars_score

                except:

                    print('Participant not found in QAP')

            if update:

                params.to_csv('subj_params.csv')

        except:

            print('Error processing participant')


def icc_peer(subject_list, gsr=False, update=False, scan=1):

    for name in subject_list:

        xb = int(params.loc[name, 'x_start']); xe = int(params.loc[name, 'x_end'])
        yb = int(params.loc[name, 'y_start']); ye = int(params.loc[name, 'y_end'])
        zb = int(params.loc[name, 'z_start']); ze = int(params.loc[name, 'z_end'])

        try:

            print('Beginning analysis on participant ' + name)

            training1 = nib.load(data_path + name + '/PEER' + str(scan) + '_resampled.nii.gz')
            training1_data = training1.get_data()
            testing = nib.load(data_path + name + '/PEER2_resampled.nii.gz')
            testing_data = testing.get_data()
            scan_count = 2

            print('starting gsr')

            if gsr:

                training1_data = gs_regress(training1_data, xb, xe, yb, ye, zb, ze)
                testing_data = gs_regress(testing_data, xb, xe, yb, ye, zb, ze)

            listed1 = []
            listed_testing = []

            print('beginning vectors')

            for tr in range(int(training1_data.shape[3])):

                tr_data1 = training1_data[xb:xe, yb:ye, zb:ze, tr]
                vectorized1 = np.array(tr_data1.ravel())
                listed1.append(vectorized1)
                te_data = testing_data[xb:xe, yb:ye, zb:ze, tr]
                vectorized_testing = np.array(te_data.ravel())
                listed_testing.append(vectorized_testing)

            train_vectors1 = np.asarray(listed1)
            train_vectors2 = []
            test_vectors = np.asarray(listed_testing)

            print('average vectors')

            train_vectors = data_processing(scan_count, train_vectors1, train_vectors2)

            # #############################################################################
            # Import coordinates for fixations

            print('importing fixations')

            fixations = pd.read_csv('stim_vals.csv')
            x_targets = np.tile(np.repeat(np.array(fixations['pos_x']), 1)*monitor_width/2, scan_count-1)
            y_targets = np.tile(np.repeat(np.array(fixations['pos_y']), 1)*monitor_height/2, scan_count-1)

            # #############################################################################
            # Create SVR Model

            predicted_x, predicted_y = create_model(train_vectors, test_vectors, x_targets, y_targets)

            # #############################################################################
            # Plot SVR predictions against targets

            # scatter_plot(name, x_targets, y_targets, predicted_x, predicted_y, plot=True, save=False)
            axis_plot(fixations, predicted_x, predicted_y)

            print('Completed participant ' + name)

            # ###############################################################################
            # Get error measurements

            x_res = []
            y_res = []

            for num in range(27):

                nums = num * 5

                for values in range(5):

                    error_x = (abs(x_targets[num] - predicted_x[nums + values]))**2
                    error_y = (abs(y_targets[num] - predicted_y[nums + values]))**2
                    x_res.append(error_x)
                    y_res.append(error_y)

            x_error = np.sqrt(np.sum(np.array(x_res))/135)
            y_error = np.sqrt(np.sum(np.array(y_res))/135)

            print([x_error, y_error])

            params.loc[name, 'x_error_' + str(scan)] = x_error
            params.loc[name, 'y_error_' + str(scan)] = y_error

            try:

                fd1 = float(qap[qap['Participant'] == name][qap['Series'] == 'func_peer_run_1']['RMSD (Mean)'])
                fd2 = float(qap[qap['Participant'] == name][qap['Series'] == 'func_peer_run_2']['RMSD (Mean)'])
                dv1 = float(qap[qap['Participant'] == name][qap['Series'] == 'func_peer_run_1']['Std. DVARS (Mean)'])
                dv2 = float(qap[qap['Participant'] == name][qap['Series'] == 'func_peer_run_2']['Std. DVARS (Mean)'])

                fd_score = np.average([[fd1, fd2]])
                dvars_score = np.average([dv1, dv2])
                params.loc[name, 'mean_fd'] = fd_score
                params.loc[name, 'dvars'] = dvars_score

            except:

                print('Participant not found in QAP')

            if update:

                params.to_csv('subj_params.csv')

        except:

            print('Error processing participant')

# #############################################################################
# Test registered data

# eye_mask = nib.load('/usr/share/fsl/5.0/data/standard/MNI152_T1_2mm_eye_mask.nii.gz')
eye_mask = nib.load('/data2/Projects/Jake/eye_masks/2mm_eye_corrected.nii.gz')
eye_mask = eye_mask.get_data()
resample_path = '/data2/Projects/Jake/Human_Brain_Mapping/'

params = pd.read_csv('peer_didactics.csv', index_col='subject', dtype=object)
reg_list = params.index.values.tolist()

def regi_peer(reg_list):

    for sub in reg_list:

        params = pd.read_csv('peer_didactics.csv', index_col='subject', dtype=object)

        print('starting participant ' + str(sub))

        scan_count = int(params.loc[sub, 'scan_count'])

        try:
            scan1 = nib.load(resample_path + sub + '/peer1_eyes_sub.nii.gz')
            scan1 = scan1.get_data()
            print('Scan 1 loaded')
            scan2 = nib.load(resample_path + sub + '/movie_TP_eyes_sub.nii.gz')
            scan2 = scan2.get_data()
            print('Scan 2 loaded')
            scan3 = nib.load(resample_path + sub + '/peer3_eyes_sub.nii.gz')
            scan3 = scan3.get_data()
            print('Scan 3 loaded')

            print('Applying eye-mask')

            for item in [scan1, scan2, scan3]:

                for vol in range(item.shape[3]):

                    output = np.multiply(eye_mask, item[:, :, :, vol])

                    item[:, :, :, vol] = output

            print('Applying mean-centering with variance-normalization and GSR')

            for item in [scan1, scan2, scan3]:

                item = mean_center_var_norm(item)
                item = gs_regress(item, 0, item.shape[0] - 1, 0, item.shape[1] - 1, 0, item.shape[2] - 1)

            listed1 = []
            listed2 = []
            listed_testing = []

            print('beginning vectors')

            for tr in range(int(scan1.shape[3])):

                tr_data1 = scan1[:, :, :, tr]
                vectorized1 = np.array(tr_data1.ravel())
                listed1.append(vectorized1)

                tr_data2 = scan3[:, :, :, tr]
                vectorized2 = np.array(tr_data2.ravel())
                listed2.append(vectorized2)

            for tr in range(int(scan2.shape[3])):

                te_data = scan2[:, :, :, tr]
                vectorized_testing = np.array(te_data.ravel())
                listed_testing.append(vectorized_testing)

            train_vectors1 = np.asarray(listed1)
            test_vectors = np.asarray(listed_testing)
            train_vectors2 = np.asarray(listed2)

            # #############################################################################
            # Averaging training signal

            print('average vectors')

            train_vectors = data_processing(3, train_vectors1, train_vectors2)

            # #############################################################################
            # Import coordinates for fixations

            print('importing fixations')

            fixations = pd.read_csv('stim_vals.csv')
            x_targets = np.tile(np.repeat(np.array(fixations['pos_x']), 1) * monitor_width / 2, 3 - 1)
            y_targets = np.tile(np.repeat(np.array(fixations['pos_y']), 1) * monitor_height / 2, 3 - 1)

            # #############################################################################
            # Create SVR Model

            x_model, y_model = create_model(train_vectors, x_targets, y_targets)

            predicted_x, predicted_y = predict_fixations(x_model, y_model, test_vectors)
            predicted_x = [np.round(float(x),3) for x in predicted_x]
            predicted_y = [np.round(float(x),3) for x in predicted_y]

            # x_targets, y_targets = axis_plot(fixations, predicted_x, predicted_y, sub, train_sets=1)
            # movie_plot(predicted_x, predicted_y, sub, train_sets=1)

            # x_corr = compute_icc(predicted_x, x_targets)
            # y_corr = compute_icc(predicted_y, y_targets)
            #
            # x_res = []
            # y_res = []
            #
            # for num in range(27):
            #
            #     nums = num * 5
            #
            #     for values in range(5):
            #         error_x = (abs(x_targets[num] - predicted_x[nums + values])) ** 2
            #         error_y = (abs(y_targets[num] - predicted_y[nums + values])) ** 2
            #         x_res.append(error_x)
            #         y_res.append(error_y)
            #
            # x_error = np.sqrt(np.sum(np.array(x_res)) / 135)
            # y_error = np.sqrt(np.sum(np.array(y_res)) / 135)
            # print([x_error, y_error])
            #
            # params.loc[sub, 'x_gsr'] = x_error
            # params.loc[sub, 'y_gsr'] = y_error
            # params.loc[sub, 'x_gsr_corr'] = x_corr
            # params.loc[sub, 'y_gsr_corr'] = y_corr
            params.loc[sub, 'x_tp'] = predicted_x
            params.loc[sub, 'y_tp'] = predicted_y
            params.to_csv('peer_didactics.csv')
            print('participant ' + str(sub) + ' complete')

        except:
            continue


# import seaborn as sns;
#
# sns.set()
#
# hm_df = pd.read_csv('subj_params.csv', index_col='subject', dtype=object)
# hm_df = hm_df.sort_values(by=['dvars'], ascending=False)
# heatmap_list = hm_df.index.values.tolist()
#
# params = pd.read_csv('peer_didactics.csv', index_col='subject', dtype=object)
#
# fixations = pd.read_csv('stim_vals.csv')
# # x_targets = np.tile(np.repeat(np.array(fixations['pos_x']), 1) * monitor_width / 2, 3 - 1)
# # y_targets = np.tile(np.repeat(np.array(fixations['pos_y']), 1) * monitor_height / 2, 3 - 1)
# x_targets = np.tile(np.repeat(np.array(fixations['pos_x']), 5) * monitor_width / 2, 1)
# y_targets = np.tile(np.repeat(np.array(fixations['pos_y']), 5) * monitor_width / 2, 1)
#
# x_hm = []
# y_hm = []
# count = 0
#
# x_temp = []
# y_temp = []
#
# for sub in heatmap_list:
#
#     try:
#
#         if count < 100:
#
#             x_out = string_to_list(params, sub, 'x_gsr_predicted')
#             y_out = string_to_list(params, sub, 'y_gsr_predicted')
#
#             print(len(x_out), len(y_out), sub)
#
#             for x in range(len(x_out)):
#                 if abs(x_out[x]) > 1000:
#                     x_out[x] = 0
#                 else:
#                     x_out[x] = x_out[x]
#
#             for x in range(len(y_out)):
#                 if abs(y_out[x]) > 1000:
#                     y_out[x] = 0
#                 else:
#                     y_out[x] = y_out[x]
#
#             x_out = np.array(x_out)
#             y_out = np.array(y_out)
#
#             x_temp.append(x_out)
#             y_temp.append(y_out)
#
#             count += 1
#
#         else:
#
#             break
#
#     except:
#
#         continue
#
# # Black line
#
# arr = np.zeros(135)
# arr = np.array([-800 for x in arr])
#
# x_temp.append(arr)
# y_temp.append(arr)
# x_temp.append(arr)
# y_temp.append(arr)
#
# for sub in range(3):
#     x_temp.append(x_targets)
#     y_temp.append(y_targets)
#
# x_hm = np.stack(x_temp)
# y_hm = np.stack(y_temp)
#
# ax = sns.heatmap(y_hm)
#
# g = sns.clustermap(y_hm, row_cluster=False)

# Add 3 subjects thick fixation line at bottom of carpet plot
# Run bash script on DM movie (isolate roi first)
# Run carpet plot across all subjects and not just ones with low motion


# #############################################################################
# Generalizable classifier


# #############################################################################
# Misc


cpac_path = '/data2/HBNcore/CMI_HBN_Data/MRI/RU/CPAC/output/pipeline_RU_CPAC/'

# eye_mask = nib.load('/usr/share/fsl/5.0/data/standard/MNI152_T1_2mm_eye_mask.nii.gz')
# eye_mask = nib.load('/data2/Projects/Jake/eye_eroded.nii.gz')
# eye_mask = eye_mask.get_data()
#
# params = pd.read_csv('subj_params.csv', index_col='subject', dtype=object)
# sub_ref = params.index.values.tolist()
#
# reg_list = []
#
# params = pd.read_csv('subj_params.csv', index_col='subject')
#
# with open('subj_params.csv', 'a') as updated_params:
#     writer = csv.writer(updated_params)
#
#     for subject in os.listdir(cpac_path):
#
#         subject = subject.replace('_ses-1', '')
#         try:
#             if int(params.loc[subject, 'scan_count']) == 3:
#                 if float(params.loc[subject, 'x_error_gsr']) < 400:
#                     if float(params.loc[subject, 'y_error_gsr']) < 400:
#                         reg_list.append(subject)
#         except:
#             continue
#
# reg_list = reg_list[:50]
#
# # with open('subj_params.csv', 'a') as updated_params:
# #     writer = csv.writer(updated_params)
# #
# #     for subject in os.listdir(cpac_path):
# #         if any(subject in x for x in sub_ref) and 'txt' not in subject:
# #             if str(params.loc[subject, 'x_error_reg']) != 'nan':
# #                 reg_list.append(subject)
#
# eye_mask = nib.load('/home/json/Desktop/peer/coef_map_threshold_90.nii.gz')
# eye_mask = eye_mask.get_data()
#
# reg_list = ['sub-5986705','sub-5375858','sub-5292617','sub-5397290','sub-5844932','sub-5787700','sub-5797959',
#             'sub-5378545','sub-5085726','sub-5984037','sub-5076391','sub-5263388','sub-5171285',
#             'sub-5917648','sub-5814325','sub-5169146','sub-5484500','sub-5481682','sub-5232535','sub-5905922',
#             'sub-5975698','sub-5986705','sub-5343770']
#
# train_set_count = len(reg_list) - 1
#
# resample_path = '/data2/Projects/Jake/Resampled/'

def general_classifier(reg_list):

    funcTime = datetime.now()

    train_vectors1 = []
    train_vectors2 = []
    test_vectors = []

    for sub in reg_list[:train_set_count]:

        print('starting participant ' + str(sub))

        scan1 = nib.load(resample_path + sub + '/peer1_eyes.nii.gz')
        scan1 = scan1.get_data()
        scan2 = nib.load(resample_path + sub + '/peer2_eyes.nii.gz')
        scan2 = scan2.get_data()
        scan3 = nib.load(resample_path + sub + '/peer3_eyes.nii.gz')
        scan3 = scan3.get_data()

        for item in [scan1, scan2, scan3]:

            for vol in range(item.shape[3]):

                output = np.multiply(eye_mask, item[:, :, :, vol])

                item[:, :, :, vol] = output

        for item in [scan1, scan2, scan3]:

            print('Initial average: ' + str(np.average(item)))
            item = mean_center_var_norm(item)
            print('Mean centered average: ' + str(np.average(item)))
            item = gs_regress(item, 0, item.shape[0]-1, 0, item.shape[1]-1, 0, item.shape[2]-1)
            print('GSR average: ' + str(np.average(item)))

        listed1 = []
        listed2 = []
        listed_testing = []

        print('beginning vectors')

        for tr in range(int(scan1.shape[3])):

            tr_data1 = scan1[:,:,:, tr]
            vectorized1 = np.array(tr_data1.ravel())
            listed1.append(vectorized1)

            tr_data2 = scan3[:,:,:, tr]
            vectorized2 = np.array(tr_data2.ravel())
            listed2.append(vectorized2)

            te_data = scan2[:,:,:, tr]
            vectorized_testing = np.array(te_data.ravel())
            listed_testing.append(vectorized_testing)

        train_vectors1.append(listed1)
        test_vectors.append(listed_testing)
        train_vectors2.append(listed2)

    full_train1 = []
    full_test = []
    full_train2 = []

    for part in range(len(reg_list[:train_set_count])):
        for vect in range(scan1.shape[3]):
            full_train1.append(train_vectors1[part][vect])
            full_test.append(test_vectors[part][vect])
            full_train2.append(train_vectors2[part][vect])

        # train_vectors1 = np.asarray(listed1)
        # test_vectors = np.asarray(listed_testing)
        # train_vectors2 = np.asarray(listed2)

        # #############################################################################
        # Averaging training signal

    print('average vectors')

    train_vectors = data_processing(3, full_train1, full_train2)

        # #############################################################################
        # Import coordinates for fixations

    print('importing fixations')

    fixations = pd.read_csv('stim_vals.csv')
    x_targets = np.tile(np.repeat(np.array(fixations['pos_x']), len(reg_list[:train_set_count])) * monitor_width / 2, 3 - 1)
    y_targets = np.tile(np.repeat(np.array(fixations['pos_y']), len(reg_list[:train_set_count])) * monitor_height / 2, 3 - 1)

        # #############################################################################
        # Create SVR Model

    x_model, y_model = create_model(train_vectors, x_targets, y_targets)
    print('Training completed: ' + str(datetime.now() - funcTime))

    for gen in range(len(reg_list)):

        gen = gen+1
        predicted_x = x_model.predict(full_test[scan1.shape[3]*(gen-1):scan1.shape[3]*(gen)])
        predicted_y = y_model.predict(full_test[scan1.shape[3]*(gen-1):scan1.shape[3]*(gen)])
        axis_plot(fixations, predicted_x, predicted_y, sub, train_sets=1)



        x_res = []
        y_res = []

        sub = reg_list[gen-1]

        for num in range(27):

            nums = num * 5

            for values in range(5):
                error_x = (abs(x_targets[num] - predicted_x[nums + values])) ** 2
                error_y = (abs(y_targets[num] - predicted_y[nums + values])) ** 2
                x_res.append(error_x)
                y_res.append(error_y)

        x_error = np.sqrt(np.sum(np.array(x_res)) / 135)
        y_error = np.sqrt(np.sum(np.array(y_res)) / 135)
        print([x_error, y_error])

        params.loc[sub, 'x_error_within'] = x_error
        params.loc[sub, 'y_error_within'] = y_error
        params.to_csv('subj_params.csv')
        print('participant ' + str(sub) + ' complete')


# #############################################################################
# Turning each set of weights into a Nifti image for coefficient of variation map analysis

# reg_list = ['sub-5986705','sub-5375858','sub-5292617','sub-5397290','sub-5844932','sub-5787700','sub-5797959',
#             'sub-5378545','sub-5085726','sub-5984037','sub-5076391','sub-5263388','sub-5171285',
#             'sub-5917648','sub-5814325','sub-5169146','sub-5484500','sub-5481682','sub-5232535','sub-5905922',
#             'sub-5975698','sub-5986705','sub-5343770']
#
# train_set_count = len(reg_list) - 1
# resample_path = '/data2/Projects/Jake/Resampled/'
# eye_mask = nib.load('/data2/Projects/Jake/Resampled/eye_all_sub.nii.gz')
# eye_mask = eye_mask.get_data()
# for sub in reg_list:
#
#     train_vectors1 = []
#     train_vectors2 = []
#     test_vectors = []
#
#     print('starting participant ' + str(sub))
#
#     scan1 = nib.load(resample_path + sub + '/peer1_eyes.nii.gz')
#     scan1 = scan1.get_data()
#     scan2 = nib.load(resample_path + sub + '/peer2_eyes.nii.gz')
#     scan2 = scan2.get_data()
#     scan3 = nib.load(resample_path + sub + '/peer3_eyes.nii.gz')
#     scan3 = scan3.get_data()
#
#     for item in [scan1, scan2, scan3]:
#
#         for vol in range(item.shape[3]):
#             output = np.multiply(eye_mask, item[:, :, :, vol])
#
#             item[:, :, :, vol] = output
#
#     for item in [scan1, scan2, scan3]:
#         print('Initial average: ' + str(np.average(item)))
#         item = mean_center_var_norm(item)
#         print('Mean centered average: ' + str(np.average(item)))
#         item = gs_regress(item, 0, item.shape[0] - 1, 0, item.shape[1] - 1, 0, item.shape[2] - 1)
#         print('GSR average: ' + str(np.average(item)))
#
#     listed1 = []
#     listed2 = []
#     listed_testing = []
#
#     print('beginning vectors')
#
#     for tr in range(int(scan1.shape[3])):
#         tr_data1 = scan1[:, :, :, tr]
#         vectorized1 = np.array(tr_data1.ravel())
#         listed1.append(vectorized1)
#
#         tr_data2 = scan3[:, :, :, tr]
#         vectorized2 = np.array(tr_data2.ravel())
#         listed2.append(vectorized2)
#
#         te_data = scan2[:, :, :, tr]
#         vectorized_testing = np.array(te_data.ravel())
#         listed_testing.append(vectorized_testing)
#
#     train_vectors1.append(listed1)
#     test_vectors.append(listed_testing)
#     train_vectors2.append(listed2)
#
#     full_train1 = []
#     full_test = []
#     full_train2 = []
#
#     for part in range(len(reg_list[:train_set_count])):
#         for vect in range(scan1.shape[3]):
#             full_train1.append(train_vectors1[part][vect])
#             full_test.append(test_vectors[part][vect])
#             full_train2.append(train_vectors2[part][vect])
#
#         # train_vectors1 = np.asarray(listed1)
#         # test_vectors = np.asarray(listed_testing)
#         # train_vectors2 = np.asarray(listed2)
#
#         # #############################################################################
#         # Averaging training signal
#
#     print('average vectors')
#
#     train_vectors = data_processing(3, full_train1, full_train2)
#
#     # #############################################################################
#     # Import coordinates for fixations
#
#     print('importing fixations')
#
#     fixations = pd.read_csv('stim_vals.csv')
#     x_targets = np.tile(np.repeat(np.array(fixations['pos_x']), len(reg_list[:train_set_count])) * monitor_width / 2, 3 - 1)
#     y_targets = np.tile(np.repeat(np.array(fixations['pos_y']), len(reg_list[:train_set_count])) * monitor_height / 2,
#                         3 - 1)
#
#     # #############################################################################
#     # Create SVR Model
#
#     x_model, y_model = create_model(train_vectors, x_targets, y_targets)
#
#     x_model_coef = x_model.coef_
#     y_model_coef = y_model.coef_
#
#     x_model_coef = np.array(x_model_coef).reshape((35, 17, 14))
#     y_model_coef = np.array(y_model_coef).reshape((35, 17, 14))
#
#     img = nib.Nifti1Image(x_model_coef, np.eye(4))
#     img.header['pixdim'] = np.array([-1, 3, 3, 3, .80500031, 0, 0, 0])
#     img.to_filename('/data2/Projects/Jake/weights_coef/' + str(sub) + 'x.nii.gz')
#     img = nib.Nifti1Image(y_model_coef, np.eye(4))
#     img.header['pixdim'] = np.array([-1, 3, 3, 3, .80500031, 0, 0, 0])
#     img.to_filename('/data2/Projects/Jake/weights_coef/' + str(sub) + 'y.nii.gz')



# #############################################################################
# Creating a coefficient of variation map

# total = nib.load('/data2/Projects/Jake/weights_coef/totalx.nii.gz')
# data = total.get_data()
#
# coef_array = np.zeros((data.shape[0], data.shape[1], data.shape[2]))
#
# for x in range(data.shape[0]):
#     for y in range(data.shape[1]):
#         for z in range(data.shape[2]):
#
#             vmean = np.mean(np.array(data[x, y, z, :]))
#             vstdev = np.std(np.array(data[x, y, z, :]))
#
#             for time in range(data.shape[3]):
#                 if np.round(vmean, 2) == 0.00:
#                     coef_array[x, y, z] = float(vstdev)
#                 else:
#                     coef_array[x, y, z] = float(vstdev)
#
# img = nib.Nifti1Image(coef_array, np.eye(4))
# img.header['pixdim'] = np.array([-1, 3, 3, 3, .80500031, 0, 0, 0])
# img.to_filename('/data2/Projects/Jake/weights_coef/x_coef_map_stdev.nii.gz')
#
# modified = nib.load('/data2/Projects/Jake/weights_coef/x_coef_map.nii.gz')
# data = modified.get_data()
#
# for x in range(data.shape[0]):
#     for y in range(data.shape[1]):
#         for z in range(data.shape[2]):
#             if abs(data[x, y, z]) > 100 or abs(data[x, y, z] < 3) and abs(np.round(data[x, y, z],2) != 0.00):
#                 data[x, y, z] = 1
#             else:
#                 data[x, y, z] = 0
#
# img = nib.Nifti1Image(data, np.eye(4))
# img.header['pixdim'] = np.array([-1, 3, 3, 3, .80500031, 0, 0, 0])
# img.to_filename('/data2/Projects/Jake/eye_masks/x_coef_map_eyes_100_5.nii.gz')

# #############################################################################
# Get distribution of voxel intensities from isolated eye coefficient of variation map to determine intensity threshold

# coef_sub = nib.load('/data2/Projects/Jake/weights_coef/x_coef_map.nii.gz')
# data = coef_sub.get_data()
#
# data_rav = data.ravel()
# data_rav = np.nan_to_num(data_rav)
# data_rav = np.array([x for x in data_rav if x != 0])
#
# xbins = np.histogram(data_rav, bins=300)[1]
#
# values, base = np.histogram(data_rav, bins=30)
# cumulative = np.cumsum(values)
#
# plt.figure()
# plt.hist(data_rav, xbins, color='b')
# plt.title('Full Raw')
# # plt.savefig('/home/json/Desktop/peer/eye_distr.png')
# plt.show()
# # plt.plot(base[:-1], cumulative/len(data_rav), color='g')
# # plt.show()

# #############################################################################
# Determine percentiles

# values, base = np.histogram(data_rav, bins=len(data_rav))
# cumulative = np.cumsum(values)/len(data_rav)
#
# for num in range(len(data_rav)):
#     if np.round(cumulative[num], 3) == .05:
#         print(base[num])
#
# # value_of_interest = base[percentile]

# #############################################################################
# Visualize error vs motion

# params = pd.read_csv('peer_didactics.csv', index_col='subject')
# params = params[params['x_gsr'] < 50000][params['y_gsr'] < 50000][params['mean_fd'] < 3.8][params['dvars'] < 1.5]
#
# # Need to fix script to not rely on indexing and instead include a subset based on mean and stdv parameters
# num_part = len(params)
#
# x_error_list = params.loc[:, 'x_gsr'][:num_part].tolist()
# y_error_list = params.loc[:, 'y_gsr'][:num_part].tolist()
# mean_fd_list = params.loc[:, 'mean_fd'][:num_part].tolist()
# dvars_list = params.loc[:, 'dvars'][:num_part].tolist()
#
# x_error_list = np.array([float(x) for x in x_error_list])
# y_error_list = np.array([float(x) for x in y_error_list])
# mean_fd_list = np.array([float(x) for x in mean_fd_list])
# dvars_list = np.array([float(x) for x in dvars_list])
#
# m1, b1 = np.polyfit(mean_fd_list, x_error_list, 1)
# m2, b2 = np.polyfit(mean_fd_list, y_error_list, 1)
# m3, b3 = np.polyfit(dvars_list, x_error_list, 1)
# m4, b4 = np.polyfit(dvars_list, y_error_list, 1)
#
# plt.figure(figsize=(8, 8))
# plt.subplot(2, 2, 1)
# plt.title('mean_fd vs. x_RMS')
# plt.scatter(mean_fd_list, x_error_list, s=5)
# plt.plot(mean_fd_list, m1*mean_fd_list + b1, '-', color='r')
# plt.subplot(2, 2, 2)
# plt.title('mean_fd vs. y_RMS')
# plt.scatter(mean_fd_list, y_error_list, s=5)
# plt.plot(mean_fd_list, m2*mean_fd_list + b2, '-', color='r')
# plt.subplot(2, 2, 3)
# plt.title('dvars vs. x_RMS')
# plt.scatter(dvars_list, x_error_list, s=5)
# plt.plot(dvars_list, m3*dvars_list + b3, '-', color='r')
# plt.subplot(2, 2, 4)
# plt.title('dvars vs. y_RMS')
# plt.scatter(dvars_list, y_error_list, s=5)
# plt.plot(dvars_list, m4*dvars_list + b4, '-', color='r')
# plt.show()

