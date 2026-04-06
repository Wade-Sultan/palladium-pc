defmodule AdminWeb.Layouts do
  @moduledoc """
  This module holds layouts and related functionality
  used by your application.
  """
  use AdminWeb, :html

  embed_templates "layouts/*"

  @doc """
  Renders the admin layout with a dark sidebar.
  Used by all Backpex resource pages and admin LiveViews.
  """
  attr :flash, :map, required: true
  attr :current_scope, :map, default: nil

  slot :inner_block, required: true

  def admin(assigns) do
    ~H"""
    <div class="flex min-h-screen bg-base-100">
      <aside class="w-64 shrink-0 bg-base-200 border-r border-base-300 flex flex-col min-h-screen sticky top-0">
        <div class="px-5 py-4 border-b border-base-300">
          <a href={~p"/admin/reference-builds"}>
            <img
              src={~p"/images/palladium-combined-dark-mode.svg"}
              alt="Palladium"
              class="h-8 w-auto"
            />
          </a>
        </div>

        <nav class="flex-1 overflow-y-auto p-3 space-y-0.5">
          <.nav_item href={~p"/admin/reference-builds"} label="Reference Builds" icon="hero-bookmark-square-mini" />

          <p class="text-xs font-semibold text-base-content/40 uppercase tracking-widest px-3 pt-5 pb-2">
            PC Parts
          </p>
          <.nav_item href={~p"/admin/cpus"} label="CPUs" icon="hero-cpu-chip-mini" />
          <.nav_item href={~p"/admin/cpu-coolers"} label="CPU Coolers" icon="hero-cpu-chip-mini" />
          <.nav_item href={~p"/admin/motherboards"} label="Motherboards" icon="hero-squares-2x2-mini" />
          <.nav_item href={~p"/admin/ram"} label="RAM Kits" icon="hero-rectangle-stack-mini" />
          <.nav_item href={~p"/admin/storage"} label="SSDs" icon="hero-circle-stack-mini" />
          <.nav_item href={~p"/admin/gpus"} label="GPUs" icon="hero-tv-mini" />
          <.nav_item href={~p"/admin/cases"} label="Cases" icon="hero-server-mini" />
          <.nav_item href={~p"/admin/psus"} label="PSUs" icon="hero-bolt-mini" />
          <.nav_item href={~p"/admin/fans"} label="Fans" icon="hero-arrow-path-mini" />

          <p class="text-xs font-semibold text-base-content/40 uppercase tracking-widest px-3 pt-5 pb-2">
            Platform
          </p>
          <.nav_item href={~p"/admin/users"} label="Users" icon="hero-users-mini" />
          <.nav_item
            href={~p"/admin/llm-analytics"}
            label="LLM Analytics"
            icon="hero-chart-bar-mini"
          />
        </nav>
      </aside>

      <div class="flex-1 min-w-0">
        {render_slot(@inner_block)}
      </div>
    </div>

    <.flash_group flash={@flash} />
    """
  end

  attr :href, :string, required: true
  attr :label, :string, required: true
  attr :icon, :string, default: nil

  defp nav_item(assigns) do
    ~H"""
    <a
      href={@href}
      class="flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm text-base-content/70 hover:bg-base-300 hover:text-base-content transition-colors"
    >
      <.icon :if={@icon} name={@icon} class="size-4 shrink-0" />
      {@label}
    </a>
    """
  end

  @doc """
  Renders the default app layout (used for non-admin pages).
  """
  attr :flash, :map, required: true
  attr :current_scope, :map, default: nil

  slot :inner_block, required: true

  def app(assigns) do
    ~H"""
    <header class="navbar px-4 sm:px-6 lg:px-8">
      <div class="flex-1">
        <a href="/" class="flex-1 flex w-fit items-center gap-2">
          <img src={~p"/images/logo.svg"} width="36" />
          <span class="text-sm font-semibold">v{Application.spec(:phoenix, :vsn)}</span>
        </a>
      </div>
      <div class="flex-none">
        <ul class="flex flex-column px-1 space-x-4 items-center">
          <li>
            <a href={~p"/admin/reference-builds"} class="btn btn-primary">Admin</a>
          </li>
        </ul>
      </div>
    </header>

    <main class="px-4 py-20 sm:px-6 lg:px-8">
      <div class="mx-auto max-w-2xl space-y-4">
        {render_slot(@inner_block)}
      </div>
    </main>

    <.flash_group flash={@flash} />
    """
  end

  @doc """
  Shows the flash group with standard titles and content.
  """
  attr :flash, :map, required: true
  attr :id, :string, default: "flash-group", doc: "the optional id of flash container"

  def flash_group(assigns) do
    ~H"""
    <div id={@id} aria-live="polite">
      <.flash kind={:info} flash={@flash} />
      <.flash kind={:error} flash={@flash} />

      <.flash
        id="client-error"
        kind={:error}
        title={gettext("We can't find the internet")}
        phx-disconnected={show(".phx-client-error #client-error") |> JS.remove_attribute("hidden")}
        phx-connected={hide("#client-error") |> JS.set_attribute({"hidden", ""})}
        hidden
      >
        {gettext("Attempting to reconnect")}
        <.icon name="hero-arrow-path" class="ml-1 size-3 motion-safe:animate-spin" />
      </.flash>

      <.flash
        id="server-error"
        kind={:error}
        title={gettext("Something went wrong!")}
        phx-disconnected={show(".phx-server-error #server-error") |> JS.remove_attribute("hidden")}
        phx-connected={hide("#server-error") |> JS.set_attribute({"hidden", ""})}
        hidden
      >
        {gettext("Attempting to reconnect")}
        <.icon name="hero-arrow-path" class="ml-1 size-3 motion-safe:animate-spin" />
      </.flash>
    </div>
    """
  end

  @doc """
  Provides dark vs light theme toggle based on themes defined in app.css.
  """
  def theme_toggle(assigns) do
    ~H"""
    <div class="card relative flex flex-row items-center border-2 border-base-300 bg-base-300 rounded-full">
      <div class="absolute w-1/3 h-full rounded-full border-1 border-base-200 bg-base-100 brightness-200 left-0 [[data-theme=light]_&]:left-1/3 [[data-theme=dark]_&]:left-2/3 transition-[left]" />

      <button
        class="flex p-2 cursor-pointer w-1/3"
        phx-click={JS.dispatch("phx:set-theme")}
        data-phx-theme="system"
      >
        <.icon name="hero-computer-desktop-micro" class="size-4 opacity-75 hover:opacity-100" />
      </button>

      <button
        class="flex p-2 cursor-pointer w-1/3"
        phx-click={JS.dispatch("phx:set-theme")}
        data-phx-theme="light"
      >
        <.icon name="hero-sun-micro" class="size-4 opacity-75 hover:opacity-100" />
      </button>

      <button
        class="flex p-2 cursor-pointer w-1/3"
        phx-click={JS.dispatch("phx:set-theme")}
        data-phx-theme="dark"
      >
        <.icon name="hero-moon-micro" class="size-4 opacity-75 hover:opacity-100" />
      </button>
    </div>
    """
  end
end
