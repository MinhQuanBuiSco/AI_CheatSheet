from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate

prompt_template = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You are a helpful assistant. Answer the user's question based on the provided context. If the context doesn't contain relevant information, say so and provide a general answer.",
        ),
        ("human", "Context: {context} \n\n Questions: {question}"),
    ]
)

cotext = "abc"
query = "xyz"
prompt = prompt_template.format_messages(context=cotext, question=query)
print(prompt)
