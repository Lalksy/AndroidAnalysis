# Common Android Memory Leaks and Potential Fix  

1. Leak: Static variables (and static views) that reference the activity directly, or indirectly by referencing inner class object, an attached view, etc.
   Fix: Clear reference in onDestory

1. Leak: Singleton manager  
   Fix: Do not pass "this" OR unregister in onDestroy

1. Reference leaked to inner class (inner class contains implicit reference to containing class)  
   Fix: use static class definition instead of anonymous/inner class  
   [But do not declare instances of the class as static fields]

1. Leak: Long running thread  
   Fix: close threads in on onDestory
