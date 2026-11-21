# Triage baseline: validation (KB val part)

## type: C=32.0, macro_f1=0.8769, acc=0.8671

```
              precision    recall  f1-score   support

      Change      0.970     0.978     0.974       231
    Incident      0.822     0.851     0.836       879
     Problem      0.729     0.682     0.705       513
     Request      0.992     0.992     0.992       664

    accuracy                          0.867      2287
   macro avg      0.878     0.876     0.877      2287
weighted avg      0.866     0.867     0.866      2287

```

## queue: C=32.0, macro_f1=0.6133, acc=0.6183

```
                                 precision    recall  f1-score   support

           Billing and Payments      0.869     0.819     0.843       243
               Customer Service      0.518     0.554     0.536       332
                General Inquiry      0.789     0.441     0.566        34
                Human Resources      0.730     0.551     0.628        49
                     IT Support      0.561     0.536     0.548       276
                Product Support      0.552     0.595     0.573       420
          Returns and Exchanges      0.693     0.550     0.613       111
            Sales and Pre-Sales      0.590     0.468     0.522        77
Service Outages and Maintenance      0.687     0.633     0.659        90
              Technical Support      0.626     0.667     0.646       655

                       accuracy                          0.618      2287
                      macro avg      0.662     0.581     0.613      2287
                   weighted avg      0.624     0.618     0.619      2287

```

## priority: C=32.0, macro_f1=0.6235, acc=0.6362

```
              precision    recall  f1-score   support

        high      0.685     0.677     0.681       908
         low      0.549     0.560     0.555       477
      medium      0.635     0.635     0.635       902

    accuracy                          0.636      2287
   macro avg      0.623     0.624     0.623      2287
weighted avg      0.637     0.636     0.636      2287

```
