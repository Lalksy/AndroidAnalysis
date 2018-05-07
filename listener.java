public class LocationListenerActivity extends Activity implements LocationUpdate{

  @Override
  public void onLocationChange(Location location){
    
  }
  
  @Override
  public void onStart(){
   LocationListener.get().register(this);
  }
  
  @Override
  public void onStop(){
   LocationListener.get().unregister(this);
  }

}