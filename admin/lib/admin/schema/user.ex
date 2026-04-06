defmodule Admin.Schema.User do
  use Ecto.Schema
  import Ecto.Changeset

  @primary_key {:id, Ecto.UUID, autogenerate: false}

  schema "users" do
    field :email, :string
    field :username, :string
    field :firebase_uid, :string
    field :is_active, :boolean, default: true
    field :is_superuser, :boolean, default: false

    timestamps(type: :utc_datetime, inserted_at: :created_at, updated_at: :updated_at)
  end

  def changeset(user, attrs, _metadata \\ %{}) do
    user
    |> cast(attrs, [:email, :username, :firebase_uid, :is_active, :is_superuser])
    |> validate_required([:email])
    |> unique_constraint(:email)
  end
end
