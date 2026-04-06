defmodule AdminWeb.Live.LLMAnalyticsLive do
  use AdminWeb, :live_view

  import Ecto.Query
  alias Admin.Repo
  alias Admin.Schema.{Conversation, Message}

  @impl true
  def mount(_params, _session, socket) do
    stats = load_stats()
    {:ok, assign(socket, stats: stats, page_title: "LLM Analytics")}
  end

  @impl true
  def render(assigns) do
    ~H"""
    <div class="p-8 space-y-8">
      <div>
        <h1 class="text-2xl font-bold text-base-content">LLM Analytics</h1>
        <p class="text-base-content/60 mt-1">Conversation and message activity overview</p>
      </div>

      <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <.stat_card label="Total Conversations" value={@stats.total_conversations} />
        <.stat_card label="Total Messages" value={@stats.total_messages} />
        <.stat_card label="User Messages" value={@stats.user_messages} />
        <.stat_card label="Assistant Messages" value={@stats.assistant_messages} />
      </div>

      <div class="card bg-base-200 border border-base-300">
        <div class="card-body">
          <h2 class="card-title text-base-content">Recent Conversations</h2>
          <div class="overflow-x-auto">
            <table class="table table-zebra">
              <thead>
                <tr>
                  <th>Title</th>
                  <th>Created</th>
                  <th>Messages</th>
                </tr>
              </thead>
              <tbody>
                <tr :for={conv <- @stats.recent_conversations}>
                  <td class="font-medium">{conv.title || "Untitled"}</td>
                  <td class="text-base-content/60 text-sm">
                    {Calendar.strftime(conv.created_at, "%b %d, %Y")}
                  </td>
                  <td>{conv.message_count}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
    """
  end

  defp stat_card(assigns) do
    ~H"""
    <div class="card bg-base-200 border border-base-300">
      <div class="card-body p-5">
        <p class="text-sm text-base-content/60">{@label}</p>
        <p class="text-3xl font-bold text-base-content mt-1">{@value}</p>
      </div>
    </div>
    """
  end

  defp load_stats do
    total_conversations = Repo.aggregate(Conversation, :count, :id)
    total_messages = Repo.aggregate(Message, :count, :id)

    user_messages =
      Repo.aggregate(from(m in Message, where: m.role == "user"), :count, :id)

    assistant_messages =
      Repo.aggregate(from(m in Message, where: m.role == "assistant"), :count, :id)

    recent_conversations =
      from(c in Conversation,
        left_join: m in Message,
        on: m.conversation_id == c.id,
        group_by: [c.id, c.title, c.created_at],
        select: %{id: c.id, title: c.title, created_at: c.created_at, message_count: count(m.id)},
        order_by: [desc: c.created_at],
        limit: 10
      )
      |> Repo.all()

    %{
      total_conversations: total_conversations,
      total_messages: total_messages,
      user_messages: user_messages,
      assistant_messages: assistant_messages,
      recent_conversations: recent_conversations
    }
  end
end
