defmodule AdminWeb.PageController do
  use AdminWeb, :controller

  def home(conn, _params) do
    render(conn, :home)
  end

  def to_admin(conn, _params) do
    redirect(conn, to: ~p"/admin/reference-builds")
  end
end
