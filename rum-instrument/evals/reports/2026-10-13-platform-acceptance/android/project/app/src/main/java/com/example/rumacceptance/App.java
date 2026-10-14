package com.example.rumacceptance;
import com.ft.sdk.*;
public class App extends android.app.Application {
 public static int initializationCount = 0;
 @Override public void onCreate() {
  super.onCreate();
  FTSdk.install(FTSDKConfig.builder(BuildConfig.RUM_DATAKIT_URL)
    .setEnv(BuildConfig.RUM_ENV).setServiceName(BuildConfig.APPLICATION_ID)
    .setEnableAccessAndroidID(false));
  FTSdk.initRUMWithConfig(new FTRUMConfig().setRumAppId(BuildConfig.RUM_APP_ID)
    .setEnableTraceUserView(false).setEnableTraceUserAction(false)
    .setEnableTraceUserResource(true).setEnableTrackAppCrash(false)
    .setEnableTraceWebView(false));
  initializationCount++;
  android.util.Log.i("RUMAcceptance", "SDK_INITIALIZED count=" + initializationCount + " appId=" + BuildConfig.RUM_APP_ID);
 }
}
