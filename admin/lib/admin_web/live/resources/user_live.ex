defmodule AdminWeb.Live.UserLive do
  use Backpex.LiveResource,
    adapter: Backpex.Adapters.Ecto,
    adapter_config: [
      repo: Admin.Repo,
      schema: Admin.Schema.User,
      update_changeset: &Admin.Schema.User.changeset/3,
      create_changeset: &Admin.Schema.User.changeset/3
    ]

  @impl Backpex.LiveResource
  def layout, do: {AdminWeb.Layouts, :admin}

  @impl Backpex.LiveResource
  def singular_name, do: "User"

  @impl Backpex.LiveResource
  def plural_name, do: "Users"

  @impl Backpex.LiveResource
  def fields do
    [
      email: %{module: Backpex.Fields.Text, label: "Email"},
      username: %{module: Backpex.Fields.Text, label: "Username"},
      firebase_uid: %{module: Backpex.Fields.Text, label: "Firebase UID", readonly: true},
      is_active: %{module: Backpex.Fields.Boolean, label: "Active"},
      is_superuser: %{module: Backpex.Fields.Boolean, label: "Superuser"}
    ]
  end
end
