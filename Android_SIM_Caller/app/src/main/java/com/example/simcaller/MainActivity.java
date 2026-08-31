package com.example.simcaller;

import android.Manifest;
import android.app.Activity;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.pm.PackageManager;
import android.net.Uri;
import android.os.Bundle;
import android.os.Handler;
import android.telephony.PhoneStateListener;
import android.telephony.TelephonyManager;
import android.view.View;
import android.widget.*;
import java.io.*;
import java.net.*;
import java.util.regex.*;

public class MainActivity extends Activity {

    private static final String BRIDGE_TOKEN = "AI_STUDENT_SYSTEM_FREE_BRIDGE_2026";

    EditText serverUrl, collegeId, username, password;
    LinearLayout loginPanel, appPanel;
    TextView status, collegeInfo, pendingList;
    Handler handler = new Handler();
    boolean running = false, inCall = false;
    long callStart = 0;
    String activeQueue = null;
    String accessToken = "";
    Runnable poller;

    @Override
    public void onCreate(Bundle b) {
        super.onCreate(b);
        setContentView(R.layout.activity_main);

        serverUrl = findViewById(R.id.serverUrl);
        collegeId = findViewById(R.id.collegeId);
        username = findViewById(R.id.username);
        password = findViewById(R.id.password);
        loginPanel = findViewById(R.id.loginPanel);
        appPanel = findViewById(R.id.appPanel);
        status = findViewById(R.id.status);
        collegeInfo = findViewById(R.id.collegeInfo);
        pendingList = findViewById(R.id.pendingList);

        SharedPreferences p = getSharedPreferences("cfg", 0);
        serverUrl.setText(p.getString("server", ""));
        collegeId.setText(p.getString("college_login_id", ""));
        username.setText(p.getString("username", ""));
        accessToken = p.getString("access_token", "");

        findViewById(R.id.login).setOnClickListener(v -> login());
        findViewById(R.id.start).setOnClickListener(v -> startPolling());
        findViewById(R.id.stop).setOnClickListener(v -> stopPolling());
        findViewById(R.id.refresh).setOnClickListener(v -> fetchPending());
        findViewById(R.id.logout).setOnClickListener(v -> logout());

        if (checkSelfPermission(Manifest.permission.CALL_PHONE) != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(new String[]{
                    Manifest.permission.CALL_PHONE,
                    Manifest.permission.READ_PHONE_STATE
            }, 101);
        }

        TelephonyManager tm = (TelephonyManager) getSystemService(TELEPHONY_SERVICE);
        tm.listen(new PhoneStateListener() {
            @Override
            public void onCallStateChanged(int state, String number) {
                if (state == TelephonyManager.CALL_STATE_OFFHOOK) {
                    inCall = true;
                    callStart = System.currentTimeMillis();
                    setStatus("📞 Call connected: " + number);
                } else if (state == TelephonyManager.CALL_STATE_IDLE && activeQueue != null) {
                    long seconds = callStart > 0
                            ? (System.currentTimeMillis() - callStart) / 1000
                            : 0;

                    String q = activeQueue;
                    activeQueue = null;
                    inCall = false;

                    postResult(q, "Success", String.valueOf(seconds),
                            "SIM call ended. Parent response is not captured by the free SIM bridge.");
                    fetchPending();
                }
            }
        }, PhoneStateListener.LISTEN_CALL_STATE);

        if (!accessToken.isEmpty() && !serverUrl.getText().toString().trim().isEmpty()) {
            showAppPanel();
            fetchPending();
        }
    }

    private void login() {
        final String base = serverUrl.getText().toString().trim().replaceAll("/$", "");
        final String cid = collegeId.getText().toString().trim();
        final String user = username.getText().toString().trim();
        final String pass = password.getText().toString();

        if (base.isEmpty() || cid.isEmpty() || user.isEmpty() || pass.isEmpty()) {
            setStatus("❌ Server URL, College ID, Username and Password are required.");
            return;
        }

        setStatus("Logging in...");

        new Thread(() -> {
            try {
                URL u = new URL(base + "/mobile/login?token=" +
                        URLEncoder.encode(BRIDGE_TOKEN, "UTF-8"));

                HttpURLConnection c = (HttpURLConnection) u.openConnection();
                c.setRequestMethod("POST");
                c.setConnectTimeout(8000);
                c.setReadTimeout(8000);
                c.setDoOutput(true);
                c.setRequestProperty("Content-Type", "application/json; charset=UTF-8");

                String body = "{"
                        + "\"college_login_id\":\"" + jsonEscape(cid) + "\","
                        + "\"username\":\"" + jsonEscape(user) + "\","
                        + "\"password\":\"" + jsonEscape(pass) + "\""
                        + "}";

                c.getOutputStream().write(body.getBytes("UTF-8"));

                int code = c.getResponseCode();
                String response = readResponse(c, code);

                if (code != 200) {
                    setStatus("❌ Login failed: " + response);
                    return;
                }

                String token = field(response, "access_token");
                String collegeName = field(response, "college_name");

                if (token == null || token.isEmpty()) {
                    setStatus("❌ Server did not return a login token.");
                    return;
                }

                accessToken = token;

                getSharedPreferences("cfg", 0).edit()
                        .putString("server", base)
                        .putString("college_login_id", cid)
                        .putString("username", user)
                        .putString("access_token", accessToken)
                        .apply();

                runOnUiThread(() -> {
                    password.setText("");
                    collegeInfo.setText("🏫 " + (collegeName == null ? cid : collegeName)
                            + "\nCollege ID: " + cid
                            + "\nUsername: " + user);
                    loginPanel.setVisibility(View.GONE);
                    appPanel.setVisibility(View.VISIBLE);
                    setStatus("✅ Login successful.");
                    fetchPending();
                });

            } catch (Exception e) {
                setStatus("❌ Connection error: " + e.getMessage());
            }
        }).start();
    }

    private void showAppPanel() {
        String cid = getSharedPreferences("cfg", 0)
                .getString("college_login_id", "");
        String user = getSharedPreferences("cfg", 0)
                .getString("username", "");

        loginPanel.setVisibility(View.GONE);
        appPanel.setVisibility(View.VISIBLE);
        collegeInfo.setText("🏫 College ID: " + cid + "\nUsername: " + user);
        setStatus("Logged in.");
    }

    private void logout() {
        stopPolling();
        accessToken = "";

        getSharedPreferences("cfg", 0).edit()
                .remove("access_token")
                .remove("college_login_id")
                .remove("username")
                .apply();

        loginPanel.setVisibility(View.VISIBLE);
        appPanel.setVisibility(View.GONE);
        pendingList.setText("");
        setStatus("Logged out.");
    }

    private void startPolling() {
        if (accessToken.isEmpty()) {
            setStatus("❌ Please login first.");
            return;
        }

        if (running) return;

        running = true;
        setStatus("▶ Automatic SIM calling started.");
        fetchPending();

        poller = new Runnable() {
            @Override
            public void run() {
                if (running && !inCall) {
                    fetchNext();
                }
                if (running) {
                    handler.postDelayed(this, 3000);
                }
            }
        };

        handler.post(poller);
    }

    private void stopPolling() {
        running = false;
        if (poller != null) handler.removeCallbacks(poller);
        setStatus("⏹ Automatic SIM calling stopped.");
    }

    private void fetchPending() {
        if (accessToken.isEmpty()) return;

        new Thread(() -> {
            try {
                String base = serverUrl.getText().toString().trim().replaceAll("/$", "");
                String url = base + "/mobile/pending-calls?access_token=" +
                        URLEncoder.encode(accessToken, "UTF-8");

                String json = get(url);
                String total = field(json, "total_calls");

                runOnUiThread(() -> {
                    if (total == null) total = "0";
                    pendingList.setText("📋 Pending Calls: " + total
                            + "\n\n" + formatPending(json));
                });
            } catch (Exception e) {
                setStatus("❌ Pending calls error: " + e.getMessage());
            }
        }).start();
    }

    private String formatPending(String json) {
        String total = field(json, "total_calls");
        if (total == null || total.equals("0")) return "No pending calls.";

        Matcher m = Pattern.compile(
                "\"parent_name\"\\s*:\\s*\"([^\"]*)\".*?\"parent_mobile\"\\s*:\\s*\"([^\"]*)\""
        ).matcher(json);

        StringBuilder out = new StringBuilder();
        int n = 1;

        while (m.find()) {
            out.append(n++)
                    .append(". ")
                    .append(m.group(1))
                    .append(" - ")
                    .append(m.group(2))
                    .append("\n");
        }

        return out.length() == 0 ? "Pending calls available." : out.toString();
    }

    private void fetchNext() {
        new Thread(() -> {
            try {
                String base = serverUrl.getText().toString().trim().replaceAll("/$", "");
                String url = base + "/mobile/next-call?access_token=" +
                        URLEncoder.encode(accessToken, "UTF-8");

                String json = get(url);

                if (json.contains("\"call\":null")) return;

                String q = field(json, "queue_id");
                String mobile = field(json, "parent_mobile");

                if (q == null || mobile == null || mobile.isEmpty()) return;

                activeQueue = q;

                runOnUiThread(() -> {
                    setStatus("📞 Calling parent: " + mobile);

                    try {
                        Intent i = new Intent(Intent.ACTION_CALL, Uri.parse("tel:" + mobile));
                        startActivity(i);
                    } catch (Exception e) {
                        activeQueue = null;
                        postResult(q, "Failed", "0",
                                "Could not start SIM call: " + e.getMessage());
                    }
                });

            } catch (Exception e) {
                setStatus("❌ Calling bridge error: " + e.getMessage());
            }
        }).start();
    }

    private void postResult(String q, String st, String dur, String remarks) {
        new Thread(() -> {
            try {
                String base = serverUrl.getText().toString().trim().replaceAll("/$", "");
                URL u = new URL(base + "/mobile/call-result?access_token=" +
                        URLEncoder.encode(accessToken, "UTF-8"));

                HttpURLConnection c = (HttpURLConnection) u.openConnection();
                c.setRequestMethod("POST");
                c.setDoOutput(true);
                c.setConnectTimeout(8000);
                c.setReadTimeout(8000);
                c.setRequestProperty("Content-Type", "application/json; charset=UTF-8");

                String body = "{\"queue_id\":" + q
                        + ",\"call_status\":\"" + jsonEscape(st)
                        + "\",\"call_duration\":\"" + jsonEscape(dur)
                        + "\",\"remarks\":\"" + jsonEscape(remarks)
                        + "\"}";

                c.getOutputStream().write(body.getBytes("UTF-8"));
                c.getInputStream().close();

            } catch (Exception e) {
                setStatus("❌ Could not save call result: " + e.getMessage());
            }
        }).start();
    }

    private String get(String s) throws Exception {
        HttpURLConnection c = (HttpURLConnection) new URL(s).openConnection();
        c.setConnectTimeout(8000);
        c.setReadTimeout(8000);

        int code = c.getResponseCode();
        String response = readResponse(c, code);
        if (code < 200 || code >= 300) {
            throw new IOException(response);
        }

        c.disconnect();
        return response;
    }

    private String readResponse(HttpURLConnection c, int code) throws Exception {
        InputStream stream = (code >= 200 && code < 400)
                ? c.getInputStream()
                : c.getErrorStream();

        if (stream == null) return "";

        BufferedReader r = new BufferedReader(new InputStreamReader(stream, "UTF-8"));
        StringBuilder b = new StringBuilder();
        String line;

        while ((line = r.readLine()) != null) {
            b.append(line);
        }

        r.close();
        return b.toString();
    }

    private String field(String json, String key) {
        Matcher m = Pattern.compile(
                "\"" + Pattern.quote(key) + "\"\\s*:\\s*\"((?:\\\\.|[^\"])*)\""
        ).matcher(json);

        if (m.find()) return m.group(1).replace("\\\"", "\"");

        Matcher n = Pattern.compile(
                "\"" + Pattern.quote(key) + "\"\\s*:\\s*(\\d+)"
        ).matcher(json);

        return n.find() ? n.group(1) : null;
    }

    private String jsonEscape(String s) {
        return s.replace("\\", "\\\\")
                .replace("\"", "\\\"")
                .replace("\n", "\\n")
                .replace("\r", "\\r");
    }

    private void setStatus(String s) {
        runOnUiThread(() -> status.setText(s));
    }
}
