from langchain_core.messages import AIMessage, HumanMessage
from langgraph.graph import MessagesState, StateGraph

from app.ingestion.document_processor import search_documents


async def doc_rag_node(state: MessagesState) -> dict:
    last_human = next(
        (m for m in reversed(state["messages"]) if isinstance(m, HumanMessage)),
        None,
    )
    if not last_human:
        return {"messages": [AIMessage(content="[Document Results]\nNo query provided.")]}

    query = last_human.content
    try:
        results = search_documents(query, k=5)
    except Exception:
        return {"messages": [AIMessage(content="[Document Results]\nError searching documents.")]}

    if not results:
        return {"messages": [AIMessage(content="[Document Results]\nNo relevant documents found.")]}

    lines = []
    for doc in results:
        meta = doc.metadata
        source = f"{meta.get('filename', '?')} (page {meta.get('page_or_slide', '?')})"
        lines.append(f"[{source}]\n{doc.page_content}")

    text = "\n---\n".join(lines)
    return {"messages": [AIMessage(content=f"[Document Results]\n{text}")]}


builder = StateGraph(MessagesState)
builder.add_node("doc_rag_node", doc_rag_node)
builder.set_entry_point("doc_rag_node")
builder.set_finish_point("doc_rag_node")

doc_rag_subgraph = builder.compile()
