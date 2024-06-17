# python-swidget
A library to manage Swidget smart devices

# Basic Usage

## Connect to the device using http/ https
```
    dev = SwidgetDimmer(host=host, token_name='x-secret-key', secret_key='password', use_https=True, use_websockets=False)
    dev.update()
    dev.turn_on()
    dev.close()
```

## Connect to the device using websockets
```
    dev = SwidgetDimmer(host=host, token_name='x-secret-key', secret_key='password', use_https=True, use_websockets=True)
    dev.start()
    dev.update()
    dev.turn_on()
    dev.close()
```
