# Interactive training or optimization

This document assumes you have some basic knowledge of `FieldSequenceModels` and how they interact with the GUI.
If not, checkout the [documentation](Browser_GUI.md).

If the purpose of your application is to train a TensorFlow model, your main application class should extend [TFModel](../phi/tf/model.py) which in turn extends `FieldSequenceModel`.
This has a couple of benefits:

- Model parameters can be saved and loaded from the GUI
- Summaries including the loss value are created and can easily be extended using `add_scalar`
- [TensorBoard](https://www.tensorflow.org/guide/summaries_and_tensorboard) can be launched from the GUI
- Profiling tools can be used in the browser
- A database is set up (see [the guide on data handling](Reading_and_Writing_Data.md))
- The `step` method is implemented by default
- Tensor nodes and database channel names can be passed to `add_field`
- Properties and the application source file are written to the output directory
- A learning rate control is available by default and more controls can be created easily using `editable_float`, `editable_int`

### Simple Example

The following toy example trains a neural network, instanced via the `network()` function to predict 
the velocity based on a density input (note that this is in general not possible, only for very simple
data sets such as the ones used in this example).

```python
from phi.tf.flow import *

class TrainingTest(TFModel):

    def __init__(self):
        TFModel.__init__(self, "Training")
        smoke = world.Smoke(Domain([64] * 2), density=placeholder, velocity=placeholder)

        with self.model_scope():
            pred_vel = network(smoke.density)
        loss = l2_loss(pred_vel - smoke.velocity)
        self.add_objective("Supervised_Loss", loss)
        
        self.set_data(train=Dataset.load('~/phi/simpleplume', range(0,8)),
                      val=Dataset.load('~/phi/simpleplume', range(8,10)),
                      placeholders=smoke.state)

        self.add_field("Velocity (Ground Truth)", smoke.velocity)
        self.add_field("Velocity (Model)", pred_vel)

app = TrainingTest().show(production=__name__!="__main__")
```

Let's go over what's happening here in detail.
First, the app calls the super constructor, passing only the app's name. Additional parameters
such as learning rate or batch size could be configured here.
Next, a fluid simulation state for a 64x64 2D flow is initialized with placeholders and added to the world.

Now the network can be built. The use of `with self.model_scope()` ensures that the network parameters can be saved and loaded automatically and from the GUI.
The `l2_loss` is part of Φ<sub>*Flow*</sub>'s n-d math package but a regular TensorFlow loss can also be used.
The inherited method `add_objective` sets up the optimizer (ADAM by default). This optimizer will be used in the default `step` implementation.

The following block sets up the data by registering the required fields (the placeholders), and by adding several sims from a data directory as training and validation data (see [the data documentation](Reading_and_Writing_Data.md) for more details).

Finally, the viewable fields are exposed to the GUI. The first line exposes the simulation velocities which was registered, while the second line exposes the graph output `pred_force` which will be recalculated each time the GUI is updated.

Lastly, the app is instantiated and the GUI created in the same way as with a [FieldSequenceModel](../phi/model.py).
You can find a full implementation of this example with a small test conv-net [as part of sources](../apps/simple_tfmodel.py).