# Triage model by language (model's validation split, kNN index = train only)

train=20552, val=2317. Thresholds: TAU_CONF=0.5, queue conf gate=0.28, SIM_THRESHOLD=0.82, HPI=0.26

## Overview

lang                            en       de       all
n                         1328.000  989.000  2317.000
type_acc                     0.947    0.907     0.930
type_f1                      0.948    0.904     0.930
type_tfidf_acc               0.876    0.817     0.851
type_char_acc                0.941    0.881     0.915
type_emb_acc                 0.918    0.895     0.908
type_conf                    0.944    0.912     0.930
queue_acc                    0.850    0.727     0.798
queue_f1                     0.849    0.708     0.794
queue_tfidf_acc              0.636    0.473     0.567
queue_char_acc               0.819    0.647     0.746
queue_emb_acc                0.789    0.674     0.740
queue_conf                   0.799    0.688     0.752
priority_acc                 0.884    0.774     0.837
priority_f1                  0.882    0.764     0.833
priority_tfidf_acc           0.677    0.556     0.625
priority_char_acc            0.852    0.697     0.785
priority_emb_acc             0.824    0.755     0.795
priority_conf                0.860    0.775     0.823
R2_low_conf_rate             0.043    0.090     0.063
R3_low_sim_rate(TAU_SIM)     0.000    0.000     0.000
top1_sim_median              0.951    0.915     0.935
hpi_recall                   0.917    0.888     0.905
lang_detect_acc              1.000    0.753     0.895

## Queue accuracy by queue x language

                                   n         acc          conf       
language                          de   en     de     en     de     en
queue                                                                
Billing and Payments              92  137  0.804  0.898  0.768  0.888
Customer Service                 138  196  0.739  0.801  0.663  0.737
General Inquiry                   16   21  0.562  0.714  0.655  0.772
Human Resources                   14   32  0.571  0.812  0.670  0.821
IT Support                       126  169  0.595  0.787  0.683  0.794
Product Support                  199  246  0.683  0.870  0.667  0.777
Returns and Exchanges             40   72  0.525  0.833  0.627  0.806
Sales and Pre-Sales               29   34  0.483  0.765  0.541  0.725
Service Outages and Maintenance   32   42  0.781  0.881  0.730  0.844
Technical Support                303  379  0.842  0.892  0.712  0.814

## Type accuracy by class x language

            n         acc          conf       
language   de   en     de     en     de     en
type                                          
Change     99  143  0.929  0.979  0.949  0.976
Incident  411  549  0.937  0.962  0.895  0.939
Problem   197  280  0.701  0.839  0.812  0.874
Request   282  356  1.000  0.994  0.992  0.994

## Billing and Payments tickets

        n  type_acc  type_conf  queue_acc  R2_rate  top1_sim_median
lang                                                               
en    137     0.978      0.952      0.898    0.051            0.959
de     92     0.946      0.939      0.804    0.065            0.925

## By dataset label x detected language

                   n  type_acc  queue_acc  priority_acc  R2_rate  top1_sim_median
label detected                                                                   
de    de         745     0.897      0.701         0.749    0.105            0.914
      en         244     0.939      0.807         0.848    0.045            0.917
en    en        1328     0.947      0.850         0.884    0.043            0.951

## By detected language (what the text really is)

             n  type_acc  queue_acc  priority_acc  R2_rate  top1_sim_median
detected                                                                   
de         745     0.897      0.701         0.749    0.105            0.914
en        1572     0.945      0.844         0.878    0.043            0.946
