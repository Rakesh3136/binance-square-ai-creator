package com.nicassistant;

import android.app.Activity;
import android.os.Bundle;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.view.View;
import android.view.Gravity;
import android.widget.*;
import org.json.*;
import java.net.*;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public class MainActivity extends Activity {
    private final ExecutorService io = Executors.newSingleThreadExecutor();
    private EditText server, chatToken, ownerToken, message;
    private final JSONArray conversationHistory = new JSONArray();
    private TextView output, status;
    private LinearLayout root;
    private static final int BG=Color.rgb(10,14,24), PANEL=Color.rgb(20,27,43), TEXT=Color.rgb(238,243,255), MUTED=Color.rgb(150,164,190), ACCENT=Color.rgb(116,145,255);
    private String base() { return server.getText().toString().trim().replaceAll("/+$", ""); }
    private GradientDrawable shape(int color, int radius, int stroke) {
        GradientDrawable d=new GradientDrawable(); d.setColor(color); d.setCornerRadius(radius);
        if(stroke!=0)d.setStroke(1,stroke); return d;
    }
    private LinearLayout column() { LinearLayout l=new LinearLayout(this); l.setOrientation(LinearLayout.VERTICAL); return l; }
    private void pad(View v,int l,int t,int r,int b){v.setPadding(l,t,r,b);}
    private TextView label(String s,int size,int color,boolean bold) {
        TextView t=new TextView(this); t.setText(s); t.setTextSize(size); t.setTextColor(color);
        if(bold)t.setTypeface(Typeface.DEFAULT,Typeface.BOLD); return t;
    }
    private void gap(LinearLayout parent,int h){ View v=new View(this); parent.addView(v,new LinearLayout.LayoutParams(1,h)); }
    private LinearLayout card() {
        LinearLayout c=column(); c.setBackground(shape(PANEL,24,Color.rgb(39,51,76))); pad(c,18,16,18,16);
        LinearLayout.LayoutParams p=new LinearLayout.LayoutParams(-1,-2); p.bottomMargin=14; root.addView(c,p); return c;
    }
    private void featureTile(LinearLayout parent,String icon,String title,String detail,boolean active) {
        LinearLayout tile=column(); tile.setBackground(shape(Color.rgb(16,24,39),18,Color.rgb(42,57,84))); pad(tile,14,13,14,13);
        TextView symbol=label(icon,20,ACCENT,true); tile.addView(symbol);
        TextView name=label(title,15,TEXT,true); LinearLayout.LayoutParams np=new LinearLayout.LayoutParams(-1,-2); np.topMargin=7; tile.addView(name,np);
        TextView desc=label(detail,11,MUTED,false); LinearLayout.LayoutParams dp=new LinearLayout.LayoutParams(-1,-2); dp.topMargin=3; tile.addView(desc,dp);
        TextView state=label(active?"AVAILABLE":"IN DEVELOPMENT",9,active?Color.rgb(84,214,160):Color.rgb(255,205,112),true);
        LinearLayout.LayoutParams sp=new LinearLayout.LayoutParams(-1,-2); sp.topMargin=9; tile.addView(state,sp);
        LinearLayout.LayoutParams p=new LinearLayout.LayoutParams(0,-2,1f); p.setMargins(0,0,7,0); parent.addView(tile,p);
    }
    private EditText field(LinearLayout parent,String hint,boolean secret) {
        EditText e=new EditText(this); e.setSingleLine(true); e.setTextColor(TEXT); e.setHintTextColor(MUTED); e.setHint(hint);
        e.setTextSize(14); e.setBackground(shape(Color.rgb(12,18,31),14,Color.rgb(48,62,91))); pad(e,14,9,14,9);
        if(secret)e.setInputType(129);
        LinearLayout.LayoutParams p=new LinearLayout.LayoutParams(-1,-2); p.topMargin=8; parent.addView(e,p); return e;
    }
    private Button button(LinearLayout parent,String text,Runnable action) {
        Button b=new Button(this); b.setText(text); b.setTextColor(Color.WHITE); b.setAllCaps(false); b.setTextSize(14);
        b.setBackground(shape(ACCENT,16,0)); LinearLayout.LayoutParams p=new LinearLayout.LayoutParams(-1,-2); p.topMargin=12; parent.addView(b,p);
        b.setOnClickListener(v->action.run()); return b;
    }
    private void show(String text){runOnUiThread(()->output.setText(text));}
    private void work(String label,Task task){
        status.setText(label+"…");
        io.execute(()->{try{String result=task.run();runOnUiThread(()->status.setText("Connected · ready"));show(result);}
            catch(Exception e){runOnUiThread(()->status.setText("Connection issue · check setup"));show(e.getMessage()==null?"Request failed":e.getMessage());}});
    }
    private boolean configured(){
        if(base().isEmpty()||base().contains("YOUR-NIC-SERVER")){
            status.setText("Backend not connected · setup required");
            show("NIC's cloud server has not been deployed or configured yet. Add the real HTTPS server address when deployment is ready.");
            return false;
        }
        if(!base().startsWith("https://")){show("For security, NIC requires an HTTPS server address.");return false;}
        return true;
    }
    private String request(String path,String token,JSONObject body)throws Exception{
        URL url=new URL(base()+path); HttpURLConnection c=(HttpURLConnection)url.openConnection();
        c.setConnectTimeout(12000);c.setReadTimeout(30000);c.setRequestMethod(body==null?"GET":"POST");
        c.setRequestProperty("Accept","application/json");
        if(token!=null&&!token.isEmpty())c.setRequestProperty("Authorization","Bearer "+token);
        if(body!=null){c.setDoOutput(true);c.setRequestProperty("Content-Type","application/json; charset=utf-8");
            try(OutputStream os=c.getOutputStream()){os.write(body.toString().getBytes(StandardCharsets.UTF_8));}}
        int code=c.getResponseCode();InputStream in=code>=400?c.getErrorStream():c.getInputStream();
        ByteArrayOutputStream bytes=new ByteArrayOutputStream();
        if(in!=null){byte[]buf=new byte[4096];int n;while((n=in.read(buf))!=-1)bytes.write(buf,0,n);in.close();}
        c.disconnect();String text=bytes.toString("UTF-8");
        if(code<200||code>=300)throw new IOException("HTTP "+code+": "+text);return text;
    }
    interface Task{String run()throws Exception;}
    @Override public void onCreate(Bundle state){
        super.onCreate(state); getWindow().setStatusBarColor(BG);getWindow().setNavigationBarColor(BG);
        getWindow().getDecorView().setSystemUiVisibility(0);
        ScrollView scroll=new ScrollView(this);scroll.setFillViewport(true);scroll.setBackgroundColor(BG);
        root=column();pad(root,20,22,20,28);scroll.addView(root);setContentView(scroll);
        LinearLayout hero=column();pad(hero,2,8,2,20);root.addView(hero);
        TextView eyebrow=label("YOUR PERSONAL AI COMPANION",11,ACCENT,true);hero.addView(eyebrow);
        TextView title=label("NIC",42,TEXT,true);hero.addView(title);
        TextView sub=label("Your personal AI command center",15,MUTED,false);hero.addView(sub);gap(hero,14);
        LinearLayout statusCard=column();statusCard.setBackground(shape(Color.rgb(24,35,54),18,Color.rgb(55,76,116)));pad(statusCard,16,13,16,13);hero.addView(statusCard);
        status=label("●  Backend not connected · setup required",13,Color.rgb(255,205,112),true);statusCard.addView(status);
        TextView setupNote=label("Your app is installed. NIC's secure cloud service still needs deployment.",12,MUTED,false);statusCard.addView(setupNote);
        LinearLayout workspace=card();
        workspace.addView(label("YOUR NIC WORKSPACE",11,ACCENT,true)); gap(workspace,4);
        workspace.addView(label("One companion. Multiple capabilities.",19,TEXT,true));
        workspace.addView(label("A clear view of what is available now and what is still being built.",12,MUTED,false));
        LinearLayout rowOne=new LinearLayout(this); rowOne.setOrientation(LinearLayout.HORIZONTAL);
        LinearLayout.LayoutParams rp=new LinearLayout.LayoutParams(-1,-2); rp.topMargin=14; workspace.addView(rowOne,rp);
        featureTile(rowOne,"✦","Assistant","Secure chat bridge",true);
        featureTile(rowOne,"▣","Workspace","Browser and files",false);
        LinearLayout rowTwo=new LinearLayout(this); rowTwo.setOrientation(LinearLayout.HORIZONTAL);
        LinearLayout.LayoutParams r2=new LinearLayout.LayoutParams(-1,-2); r2.topMargin=8; workspace.addView(rowTwo,r2);
        featureTile(rowTwo,"◇","Specialists","Dynamic agent tools",false);
        featureTile(rowTwo,"↗","Creator Studio","Research and rewards",false);
        LinearLayout design=column(); design.setBackground(shape(Color.rgb(25,35,57),18,Color.rgb(68,85,128))); pad(design,15,13,15,13);
        LinearLayout.LayoutParams designP=new LinearLayout.LayoutParams(-1,-2); designP.topMargin=12; workspace.addView(design,designP);
        design.addView(label("NIC DESIGN LAB",10,ACCENT,true));
        TextView designText=label("Design Intelligence is being built to propose, preview and test improvements. Production changes stay under your approval.",12,MUTED,false);
        LinearLayout.LayoutParams dt=new LinearLayout.LayoutParams(-1,-2); dt.topMargin=5; design.addView(designText,dt);
        LinearLayout connection=card();
        connection.addView(label("01  CONNECTION",11,ACCENT,true));gap(connection,5);
        connection.addView(label("Connect your NIC server",19,TEXT,true));
        TextView expl=label("The server address will be provided after the backend is deployed.",12,MUTED,false);connection.addView(expl);
        server=field(connection,"https://your-secure-nic-server",false);server.setText(BuildConfig.DEFAULT_SERVER_URL);
        chatToken=field(connection,"Chat access token · session only",true);
        ownerToken=field(connection,"Owner control token · session only",true);
        button(connection,"Check connection",()->{if(configured())work("Checking server",()->request("/healthz",null,null));});
        LinearLayout chat=card();
        chat.addView(label("02  CONVERSATION",11,ACCENT,true));gap(chat,5);
        chat.addView(label("Talk to NIC",21,TEXT,true));
        chat.addView(label("Ask questions, assign tasks and review what NIC is doing.",12,MUTED,false));
        message=new EditText(this);message.setTextColor(TEXT);message.setHintTextColor(MUTED);message.setHint("Message NIC…");message.setTextSize(15);message.setMinLines(3);
        message.setGravity(Gravity.TOP);message.setBackground(shape(Color.rgb(12,18,31),16,Color.rgb(48,62,91)));pad(message,14,12,14,12);
        LinearLayout.LayoutParams mp=new LinearLayout.LayoutParams(-1,-2);mp.topMargin=12;chat.addView(message,mp);
        button(chat,"Send to NIC  →",()->{
            String prompt=message.getText().toString().trim();if(prompt.isEmpty()){show("Write a message first.");return;}if(!configured())return;
            work("Sending message",()->{
                JSONObject body=new JSONObject();body.put("message",prompt);synchronized(conversationHistory){body.put("history",conversationHistory);}
                JSONObject response=new JSONObject(request("/chat",chatToken.getText().toString(),body));
                String reply=response.optString("reply","No reply returned");
                JSONObject u=new JSONObject();u.put("role","user");u.put("content",prompt);
                JSONObject a=new JSONObject();a.put("role","assistant");a.put("content",reply);
                synchronized(conversationHistory){conversationHistory.put(u);conversationHistory.put(a);while(conversationHistory.length()>24)conversationHistory.remove(0);}
                return reply;
            });
        });
        LinearLayout activity=card();
        activity.addView(label("03  TRANSPARENCY",11,ACCENT,true));gap(activity,5);
        activity.addView(label("Owner activity",20,TEXT,true));
        activity.addView(label("See recorded tasks and outcomes. Hidden reasoning is never exposed.",12,MUTED,false));
        button(activity,"Refresh activity journal",()->{if(!configured())return;work("Loading activity",()->{
            JSONObject data=new JSONObject(request("/activity",ownerToken.getText().toString(),null));JSONArray events=data.optJSONArray("events");
            if(events==null||events.length()==0)return"No activity events recorded yet.";
            StringBuilder out=new StringBuilder();for(int i=0;i<events.length();i++){JSONObject e=events.getJSONObject(i);
                out.append(e.optString("created_at")).append(" · ").append(e.optString("actor")).append(" / ").append(e.optString("action"))
                .append(" · ").append(e.optString("status")).append("\n").append(e.optString("summary")).append("\n\n");}
            return out.toString();
        });});
        LinearLayout result=card();result.addView(label("NIC RESPONSE",11,ACCENT,true));gap(result,6);
        output=label("When the backend is connected, NIC's replies and activity will appear here.",14,MUTED,false);output.setTextIsSelectable(true);result.addView(output);
        TextView security=label("SECURITY  ·  Tokens remain in memory for this session only. Chat and owner access are separate. HTTPS required.",11,MUTED,false);
        pad(security,4,4,4,8);root.addView(security);
    }
    @Override protected void onDestroy(){super.onDestroy();io.shutdownNow();}
}