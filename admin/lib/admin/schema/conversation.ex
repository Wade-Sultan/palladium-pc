defmodule Admin.Schema.Conversation do
  use Ecto.Schema

  @primary_key {:id, Ecto.UUID, autogenerate: false}
  @foreign_key_type Ecto.UUID

  schema "conversations" do
    field :user_id, Ecto.UUID
    field :build_id, Ecto.UUID
    field :title, :string
    field :summary, :string

    timestamps(type: :utc_datetime, inserted_at: :created_at, updated_at: :updated_at)
  end
end
