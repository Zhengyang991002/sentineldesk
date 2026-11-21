# Triage baseline: validation (KB val part)

## type: C=8.0, macro_f1=0.8774, acc=0.8666

```
              precision    recall  f1-score   support

      Change      0.978     0.974     0.976       231
    Incident      0.824     0.844     0.834       879
     Problem      0.722     0.690     0.706       513
     Request      0.992     0.995     0.994       664

    accuracy                          0.867      2287
   macro avg      0.879     0.876     0.877      2287
weighted avg      0.866     0.867     0.866      2287

```

## queue: C=32.0, macro_f1=0.6105, acc=0.6165

```
                                 precision    recall  f1-score   support

           Billing and Payments      0.870     0.823     0.846       243
               Customer Service      0.514     0.548     0.531       332
                General Inquiry      0.789     0.441     0.566        34
                Human Resources      0.692     0.551     0.614        49
                     IT Support      0.563     0.547     0.555       276
                Product Support      0.554     0.595     0.574       420
          Returns and Exchanges      0.693     0.550     0.613       111
            Sales and Pre-Sales      0.590     0.468     0.522        77
Service Outages and Maintenance      0.667     0.622     0.644        90
              Technical Support      0.623     0.660     0.641       655

                       accuracy                          0.617      2287
                      macro avg      0.656     0.580     0.610      2287
                   weighted avg      0.622     0.617     0.617      2287

```

## priority: C=32.0, macro_f1=0.6219, acc=0.6345

```
              precision    recall  f1-score   support

        high      0.680     0.674     0.677       908
         low      0.548     0.560     0.554       477
      medium      0.636     0.634     0.635       902

    accuracy                          0.634      2287
   macro avg      0.621     0.623     0.622      2287
weighted avg      0.635     0.634     0.635      2287

```
