package com.example.rumacceptance;
import com.ft.sdk.*;
import okhttp3.*;
public class MainActivity extends android.app.Activity {
 @Override public void onCreate(android.os.Bundle state) {
  super.onCreate(state);
  android.widget.EditText input = new android.widget.EditText(this);
  input.setText("INPUT_CANARY_ANDROID_ACCEPTANCE"); setContentView(input);
  FTRUMGlobalManager.get().startView("AcceptanceHome");
  FTRUMGlobalManager.get().addError("java.lang.IllegalStateException: synthetic acceptance error\n at com.example.rumacceptance.MainActivity.onCreate(MainActivity.java:12)", "SyntheticAcceptanceError", "java");
  new Thread(() -> {
   OkHttpClient client = new OkHttpClient.Builder()
     .addInterceptor(new FTResourceInterceptor())
     .eventListenerFactory(new FTResourceEventListener.FTFactory()).build();
   Request req = new Request.Builder().url("http://127.0.0.1:19530/resource")
     .header("Authorization", "Bearer HEADER_CANARY_ANDROID_ACCEPTANCE")
     .post(RequestBody.create(MediaType.get("text/plain"), "BODY_CANARY_ANDROID_ACCEPTANCE")).build();
   try (Response response = client.newCall(req).execute()) {
    android.util.Log.i("RUMAcceptance", "RESOURCE_HTTP status=" + response.code() + " body=" + response.body().string());
   } catch (Exception e) { android.util.Log.e("RUMAcceptance", "RESOURCE_FAILED", e); }
   runOnUiThread(() -> new android.os.Handler().postDelayed(() -> {
    FTRUMGlobalManager.get().stopView(); FTSdk.flushSyncData();
    android.util.Log.i("RUMAcceptance", "SIGNALS_COMPLETED");
   }, 2500));
  }).start();
 }
}
