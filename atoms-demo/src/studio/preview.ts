const PREVIEW_CHANNEL = 'quality-agent-studio-preview-storage';

export function buildPreviewDocument(html: string, projectId: string): string {
  const csp = [
    "default-src 'none'",
    "script-src 'unsafe-inline'",
    "style-src 'unsafe-inline'",
    'img-src data: blob:',
    'font-src data:',
    "connect-src 'none'",
    "media-src 'none'",
    "object-src 'none'",
    "frame-src 'none'",
    "form-action 'none'",
  ].join('; ');
  const bridge = `<script>(function(){
    const channel=${JSON.stringify(PREVIEW_CHANNEL)};
    const projectId=${JSON.stringify(projectId)};
    const pending=new Map();
    let sequence=0;
    function request(action,key,value){
      return new Promise((resolve,reject)=>{
        const requestId='storage-'+(++sequence)+'-'+Date.now();
        pending.set(requestId,{resolve,reject});
        window.parent.postMessage({channel,projectId,requestId,action,key,value},'*');
        setTimeout(()=>{if(pending.has(requestId)){pending.delete(requestId);reject(new Error('存储请求超时'));}},3000);
      });
    }
    window.demoStorage={
      get:(key)=>request('get',key),
      set:(key,value)=>request('set',key,value),
      remove:(key)=>request('remove',key)
    };
    window.addEventListener('message',(event)=>{
      const data=event.data;
      if(event.source!==window.parent||!data||data.channel!==channel||data.projectId!==projectId)return;
      const entry=pending.get(data.requestId);
      if(!entry)return;
      pending.delete(data.requestId);
      if(data.error)entry.reject(new Error(data.error));else entry.resolve(data.value);
    });
  })();<\/script>`;
  const securityHead = `<meta http-equiv="Content-Security-Policy" content="${csp}">${bridge}`;
  return /<head[^>]*>/i.test(html)
    ? html.replace(/<head([^>]*)>/i, `<head$1>${securityHead}`)
    : html.replace(/<html([^>]*)>/i, `<html$1><head>${securityHead}</head>`);
}

export function installPreviewStorageBridge(
  iframe: HTMLIFrameElement,
  projectId: string,
): () => void {
  const storageKey = `quality_agent_preview_${projectId}`;
  const onMessage = (event: MessageEvent) => {
    if (event.source !== iframe.contentWindow) return;
    const data = event.data as Record<string, unknown> | null;
    if (!data || data.channel !== PREVIEW_CHANNEL || data.projectId !== projectId) return;
    const requestId = typeof data.requestId === 'string' ? data.requestId : '';
    const action = typeof data.action === 'string' ? data.action : '';
    const key = typeof data.key === 'string' ? data.key : '';
    if (!requestId || !['get', 'set', 'remove'].includes(action) || !key || key.length > 100) return;

    const reply = (payload: Record<string, unknown>) => iframe.contentWindow?.postMessage({
      channel: PREVIEW_CHANNEL,
      projectId,
      requestId,
      ...payload,
    }, '*');

    try {
      const values = JSON.parse(localStorage.getItem(storageKey) ?? '{}') as Record<string, unknown>;
      if (action === 'get') {
        reply({ value: values[key] ?? null });
        return;
      }
      if (action === 'remove') delete values[key];
      if (action === 'set') {
        const serializedValue = JSON.stringify(data.value);
        if (serializedValue.length > 100_000) throw new Error('单项数据不能超过 100 KB');
        values[key] = data.value;
      }
      const serialized = JSON.stringify(values);
      if (serialized.length > 500_000) throw new Error('应用数据不能超过 500 KB');
      localStorage.setItem(storageKey, serialized);
      reply({ value: true });
    } catch (error) {
      reply({ error: error instanceof Error ? error.message : '存储失败' });
    }
  };
  window.addEventListener('message', onMessage);
  return () => window.removeEventListener('message', onMessage);
}
