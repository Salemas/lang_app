<script>
  import { onMount } from "svelte";

  let chats = $state([]);
  let activeChatId = $state(null);
  let input = $state("");
  let loading = $state(false);
  let streamingText = $state("");
  let container = $state(null);
  let rightOpen = $state(false);
  let showIngestDialog = $state(false);
  let ingestFile = $state(null);
  let ingestStatus = $state("");
  let ingestUploading = $state(false);
  let docFile = $state(null);
  let docUploadStatus = $state("");
  let docUploading = $state(false);
  let uploadedDocs = $state([]);
  let pricelistIngestions = $state([]);

  let currentModel = $state("");
  let availableModels = $state([]);

  let activeChat = $derived(chats.find(c => c.id === activeChatId));

  async function loadDocuments() {
    try {
      const res = await fetch("http://localhost:8000/documents");
      uploadedDocs = await res.json();
    } catch { /* ignore */ }
  }

  async function loadPricelistIngestions() {
    try {
      const res = await fetch("http://localhost:8000/pricelist/ingestions");
      pricelistIngestions = await res.json();
    } catch { /* ignore */ }
  }

  async function deletePricelistIngestion(uploadId) {
    await fetch(`http://localhost:8000/pricelist/ingestions/${uploadId}`, { method: "DELETE" });
    await loadPricelistIngestions();
  }

  async function deleteDocument(docId) {
    await fetch(`http://localhost:8000/documents/${docId}`, { method: "DELETE" });
    uploadedDocs = uploadedDocs.filter(d => d.doc_id !== docId);
  }

  async function loadModel() {
    try {
      const res = await fetch("http://localhost:8000/settings/model");
      const data = await res.json();
      currentModel = data.model;
      availableModels = data.available_models;
    } catch { /* ignore */ }
  }

  async function updateModel(model) {
    try {
      const res = await fetch("http://localhost:8000/settings/model", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ model }),
      });
      if (res.ok) currentModel = model;
    } catch { /* ignore */ }
  }

  function fmtDate(iso) {
    if (!iso) return "";
    const d = new Date(iso);
    return d.toLocaleDateString() + " " + d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  }

  onMount(async () => {
    await loadModel();
    await loadPricelistIngestions();
    const res = await fetch("http://localhost:8000/chats");
    chats = await res.json();
    if (chats.length > 0) {
      activeChatId = chats[0].id;
      await loadMessages(chats[0].id);
    }
    await loadDocuments();
  });

  async function loadMessages(chatId) {
    const res = await fetch(`http://localhost:8000/chats/${chatId}/messages`);
    const data = await res.json();
    const chat = chats.find(c => c.id === chatId);
    if (chat) chat.messages = data;
  }

  async function newChat() {
    const res = await fetch("http://localhost:8000/chats", { method: "POST" });
    const chat = await res.json();
    chat.messages = [];
    chats = [chat, ...chats];
    activeChatId = chat.id;
    input = "";
  }

  async function deleteChat(e, id) {
    e.stopPropagation();
    await fetch(`http://localhost:8000/chats/${id}`, { method: "DELETE" });
    const idx = chats.findIndex(c => c.id === id);
    chats = chats.filter(c => c.id !== id);
    if (activeChatId === id) {
      activeChatId = chats.length > 0
        ? chats[Math.min(idx, chats.length - 1)].id
        : null;
    }
  }

  function selectChat(id) {
    if (id !== activeChatId) {
      activeChatId = id;
      input = "";
      const chat = chats.find(c => c.id === id);
      if (chat && !chat.messages) loadMessages(id);
    }
  }

  function scroll() {
    requestAnimationFrame(() => {
      if (container) container.scrollTop = container.scrollHeight;
    });
  }

  async function send() {
    if (!input.trim() || loading || !activeChat) return;
    const userMsg = input;
    input = "";
    activeChat.messages = [
      ...(activeChat.messages || []),
      { role: "user", content: userMsg },
    ];
    loading = true;
    streamingText = "";
    scroll();

    try {
      const res = await fetch("http://localhost:8000/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: userMsg, chat_id: activeChat.id }),
      });

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop();
        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          const data = line.slice(6).trim();
          if (data === "[DONE]") break;
          const parsed = JSON.parse(data);
          streamingText += parsed.content;
          scroll();
        }
      }

      activeChat.messages.push({ role: "assistant", content: streamingText });
    } catch {
      activeChat.messages.push({
        role: "assistant",
        content: "Error: could not reach server",
      });
    } finally {
      streamingText = "";
      loading = false;
    }
  }

  function keydown(e) {
    if (e.key === "Enter") send();
  }
</script>

<div class="layout">
  <aside>
    <button class="new" onclick={newChat}>+ New Chat</button>
    <div class="list">
      {#each chats as chat (chat.id)}
        <div
          class="item"
          class:active={chat.id === activeChatId}
          onclick={() => selectChat(chat.id)}
          onkeydown={(e) => { if (e.key === "Enter") selectChat(chat.id); }}
          role="button"
          tabindex="0"
        >
          <span>{chat.title}</span>
          <button class="del" onclick={(e) => deleteChat(e, chat.id)}>x</button>
        </div>
      {/each}
    </div>
  </aside>

  <main>
    <button class="toggle-right" onclick={() => rightOpen = !rightOpen}>
      {rightOpen ? "✕" : "☰"}
    </button>
    {#if activeChat}
      <div class="center">
        <div class="chat" bind:this={container}>
          {#each (activeChat.messages || []) as msg}
            <div class="msg {msg.role}">{msg.content}</div>
          {/each}
          {#if loading && !streamingText}
            <div class="msg assistant thinking">
              <span class="dots"><span>.</span><span>.</span><span>.</span></span>
            </div>
          {/if}
          {#if streamingText}
            <div class="msg assistant">{streamingText}</div>
          {/if}
        </div>
        <div class="bar">
          <input
            type="text"
            bind:value={input}
            onkeydown={keydown}
            placeholder="Type a message..."
            disabled={loading}
          />
          <button onclick={send} disabled={loading}>Send</button>
        </div>
      </div>
    {:else}
      <div class="center">
        <div class="empty">
          <h2>Lang App</h2>
          <p>Click <strong>+ New Chat</strong> to start.</p>
        </div>
      </div>
    {/if}
  </main>

{#if rightOpen}
  <div class="backdrop" role="presentation" onclick={() => rightOpen = false} onkeydown={() => rightOpen = false}></div>
  <aside class="right-panel">
    <h3>App Settings</h3>
    <div class="section">
      <h4>Model</h4>
      <select
        value={currentModel}
        onchange={(e) => updateModel(e.target.value)}
      >
        {#each availableModels as m}
          <option value={m} selected={m === currentModel}>{m}</option>
        {/each}
      </select>
    </div>
    <div class="section">
      <h4>Data Ingestion</h4>
      <button onclick={() => showIngestDialog = true}>Upload Pricelist</button>
      {#if pricelistIngestions.length > 0}
        <div class="ingestion-list">
          {#each pricelistIngestions as ing (ing.id)}
            <div class="ingestion-item">
              <span class="ingestion-name" title={ing.filename}>{ing.filename}</span>
              <span class="ingestion-meta">{ing.row_count} rows &middot; {fmtDate(ing.uploaded_at)}</span>
              <button class="del" onclick={() => deletePricelistIngestion(ing.id)}>x</button>
            </div>
          {/each}
        </div>
      {:else}
        <p class="placeholder">No pricelist data ingested</p>
      {/if}
    </div>
    <div class="section">
      <h4>Document Upload</h4>
      <input
        type="file"
        accept=".pdf,.pptx,.ppt"
        onchange={(e) => { docFile = e.target.files[0]; docUploadStatus = ""; }}
        disabled={docUploading}
      />
      <button
        onclick={async () => {
          if (!docFile) return;
          docUploading = true;
          docUploadStatus = "Uploading...";
          const form = new FormData();
          form.append("file", docFile);
          try {
            const res = await fetch("http://localhost:8000/documents/upload", {
              method: "POST",
              body: form,
            });
            const data = await res.json();
            if (!res.ok) {
              docUploadStatus = `Error: ${data.error || "upload failed"}`;
            } else {
              docUploadStatus = `Success: ${data.chunks} chunks indexed.`;
            }
            docFile = null;
            await loadDocuments();
          } catch {
            docUploadStatus = "Error: upload failed.";
          } finally {
            docUploading = false;
          }
        }}
        disabled={!docFile || docUploading}
      >
        {docUploading ? "Uploading..." : "Upload"}
      </button>
      {#if docUploadStatus}
        <p class="status">{docUploadStatus}</p>
      {/if}
      {#if uploadedDocs.length > 0}
        <div class="doc-list">
          {#each uploadedDocs as doc (doc.doc_id)}
            <div class="doc-item">
              <span class="doc-name" title={doc.filename}>
                {doc.filename} ({doc.chunks} chunks)
              </span>
              <span class="doc-date">{fmtDate(doc.uploaded_at)}</span>
              <button class="del" onclick={() => deleteDocument(doc.doc_id)}>x</button>
            </div>
          {/each}
        </div>
      {:else}
        <p class="placeholder">No documents uploaded</p>
      {/if}
    </div>
  </aside>
{/if}

{#if showIngestDialog}
  <div class="backdrop" role="presentation" onclick={() => { showIngestDialog = false; ingestFile = null; ingestStatus = ""; }} onkeydown={() => { showIngestDialog = false; ingestFile = null; ingestStatus = ""; }}></div>
  <div class="dialog">
    <h3>Upload Pricelist</h3>
    <p>Select a .xlsx or .csv file with pricelist data.</p>
    <input
      type="file"
      accept=".xlsx,.csv"
      onchange={(e) => { ingestFile = e.target.files[0]; ingestStatus = ""; }}
      disabled={ingestUploading}
    />
    <div class="dialog-actions">
      <button
        onclick={async () => {
          if (!ingestFile) return;
          ingestUploading = true;
          ingestStatus = "Uploading...";
          const form = new FormData();
          form.append("file", ingestFile);
          try {
            const res = await fetch("http://localhost:8000/pricelist/upload", {
              method: "POST",
              body: form,
            });
            const data = await res.json();
            if (!res.ok) {
              ingestStatus = `Error: ${data.error || "upload failed"}`;
            } else {
              ingestStatus = `Success: ${data.imported} rows imported.`;
              await loadPricelistIngestions();
            }
            ingestFile = null;
          } catch {
            ingestStatus = "Error: upload failed.";
          } finally {
            ingestUploading = false;
          }
        }}
        disabled={!ingestFile || ingestUploading}
      >
        {ingestUploading ? "Uploading..." : "Upload"}
      </button>
      <button
        onclick={() => { showIngestDialog = false; ingestFile = null; ingestStatus = ""; }}
      >
        Cancel
      </button>
    </div>
    {#if ingestStatus}
      <p class="status">{ingestStatus}</p>
    {/if}
  </div>
{/if}
</div>

<style>
  :global(body) { margin: 0; }
  .layout { display: flex; height: 100vh; font-family: sans-serif; }
  aside { width: 240px; background: #f5f5f5; display: flex; flex-direction: column; padding: 0.75rem; gap: 0.5rem; border-right: 1px solid #ddd; }
  .new { padding: 0.5rem; font-size: 0.95rem; cursor: pointer; border: 1px solid #ccc; border-radius: 4px; background: white; }
  .new:hover { background: #eee; }
  .list { flex: 1; overflow-y: auto; display: flex; flex-direction: column; gap: 2px; }
  .item { display: flex; align-items: center; padding: 0.4rem 0.5rem; border-radius: 4px; cursor: pointer; font-size: 0.9rem; }
  .item:hover { background: #e0e0e0; }
  .item.active { background: #d1e7ff; }
  .item span { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .del { visibility: hidden; background: none; border: none; cursor: pointer; color: #999; font-size: 0.7rem; padding: 0; width: 20px; flex-shrink: 0; text-align: center; line-height: 1; }
  .right-panel .del { width: 20px; padding: 0; } /* override global right-panel button width:100% */
  .item:hover .del, .doc-item:hover .del, .ingestion-item:hover .del { visibility: visible; }
  .del:hover { color: #c00; }
  main { flex: 1; display: flex; flex-direction: column; padding: 1rem 0; overflow: hidden; }
  .center { flex: 1; width: 70%; max-width: 70%; margin: 0 auto; display: flex; flex-direction: column; overflow: hidden; }
  .empty { display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100%; color: #888; }
  .chat { flex: 1; overflow-y: auto; display: flex; flex-direction: column; gap: 0.5rem; padding: 0.5rem; border: 1px solid #ccc; border-radius: 6px; margin-bottom: 1rem; }
  .msg { padding: 0.5rem 0.75rem; border-radius: 6px; max-width: 80%; word-wrap: break-word; white-space: pre-wrap; }
  .user { align-self: flex-end; background: #d1e7ff; }
  .assistant { align-self: flex-start; background: #f0f0f0; }
  .thinking { min-height: 1.5em; display: flex; align-items: center; }
  .dots span { animation: blink 1.4s infinite both; font-size: 1.5rem; line-height: 1; }
  .dots span:nth-child(2) { animation-delay: 0.2s; }
  .dots span:nth-child(3) { animation-delay: 0.4s; }
  @keyframes blink { 0%, 80%, 100% { opacity: 0; } 40% { opacity: 1; } }
  .bar { display: flex; gap: 0.5rem; }
  input { flex: 1; padding: 0.5rem; font-size: 1rem; }
  button { padding: 0.5rem 1rem; font-size: 1rem; }
.toggle-right {
  position: fixed; top: 0.75rem; right: 0.75rem;
  z-index: 100; padding: 0.4rem 0.6rem; font-size: 1.1rem;
  cursor: pointer; border: 1px solid #ccc; border-radius: 4px;
  background: white; line-height: 1;
}
.toggle-right:hover { background: #eee; }
.backdrop {
  position: fixed; inset: 0; background: rgba(0,0,0,0.3);
  z-index: 200;
}
.right-panel {
  position: fixed; top: 0; right: 0; bottom: 0;
  width: 280px; background: white; z-index: 300;
  padding: 1rem; box-shadow: -2px 0 8px rgba(0,0,0,0.15);
  overflow-y: auto;
}
.right-panel h3 { margin: 0 0 1rem 0; font-size: 1.1rem; }
.right-panel .section { margin-bottom: 1.5rem; }
.right-panel .section h4 { margin: 0 0 0.5rem 0; font-size: 0.95rem; color: #555; }
.right-panel .placeholder { color: #999; font-style: italic; font-size: 0.85rem; }
.right-panel button { width: 100%; padding: 0.5rem; font-size: 0.9rem; }
.dialog {
  position: fixed; top: 50%; left: 50%; transform: translate(-50%, -50%);
  background: white; z-index: 400; padding: 1.5rem; border-radius: 8px;
  box-shadow: 0 4px 20px rgba(0,0,0,0.25); min-width: 360px;
}
.dialog h3 { margin: 0 0 0.5rem 0; }
.dialog p { margin: 0 0 1rem 0; color: #666; font-size: 0.9rem; }
.dialog input { display: block; margin-bottom: 1rem; }
.dialog-actions { display: flex; gap: 0.5rem; }
.dialog-actions button { flex: 1; }
.status { margin-top: 0.75rem; font-size: 0.9rem; color: #333; }
.doc-list { margin-top: 0.5rem; display: flex; flex-direction: column; gap: 2px; }
.doc-item { display: flex; align-items: center; padding: 0.3rem 0; font-size: 0.8rem; }
.doc-name { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.doc-date { font-size: 0.7rem; color: #999; white-space: nowrap; }
.ingestion-list { margin-top: 0.5rem; display: flex; flex-direction: column; gap: 2px; }
.ingestion-item { display: flex; align-items: center; gap: 0.25rem; padding: 0.25rem 0; border-bottom: 1px solid #eee; }
.ingestion-name { flex: 1; min-width: 0; font-size: 0.8rem; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.ingestion-meta { font-size: 0.7rem; color: #999; flex: 1; }
</style>
