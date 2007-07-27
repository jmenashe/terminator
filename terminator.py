#!/usr/bin/python
import sys
import string
import gtk
import vte
import gconf
import pango
import gnome
import time

class TerminatorTerm:
  lastreconfigure = 0

  # Our settings
  # FIXME: Add commandline and/or gconf options to change these
  # FIXME: Track profile default command behaviour
  defaults = {
    'profile_dir'           : '/apps/gnome-terminal/profiles/',
    'profile'               : 'Default',
    'allow_bold'            : True,
    'audible_bell'          : False,
    'background'            : None,
    'background_color'      : '#000000',
    'backspace_binding'     : 'ascii-del',
    'cursor_blinks'         : False,
    'emulation'             : 'xterm',
    'font_name'             : 'Serif 10',
    'foreground_color'      : '#AAAAAA',
    'scrollbar'             : True,
    'scroll_on_keystroke'   : False,
    'scroll_on_output'      : False,
    'scrollback_lines'      : 100,
    'focus'                 : 'sloppy',
    'visible_bell'          : False,
    'child_restart'         : True,
    'link_scheme'           : '(news|telnet|nttp|file|http|ftp|https)',
    '_link_user'            : '[%s]+(:[%s]+)?',
    'link_hostchars'        : '-A-Za-z0-9',
    'link_userchars'        : '-A-Za-z0-9',
    'link_passchars'        : '-A-Za-z0-9,?;.:/!%$^*&~"#\'',
    'palette'               : '/apps/gnome-terminal/profiles/Default/palette',
  }

  def __init__ (self, term, settings = {}):
    self.defaults['link_user'] = self.defaults['_link_user']%(self.defaults['link_userchars'], self.defaults['link_passchars'])

    # Set up any overridden settings
    for key in settings.keys ():
      defaults[key] = settings[key]

    self.term = term
    self.profile = self.defaults['profile_dir'] + self.defaults['profile']

    self.gconf_client = gconf.client_get_default ()
    self.gconf_client.add_dir (self.profile, gconf.CLIENT_PRELOAD_RECURSIVE)
    self.gconf_client.add_dir ('/apps/metacity/general', gconf.CLIENT_PRELOAD_RECURSIVE)

    self.clipboard = gtk.clipboard_get(gtk.gdk.SELECTION_CLIPBOARD)

    self._vte = vte.Terminal ()
    self.reconfigure_vte ()
    self._vte.show ()

    self._box = gtk.HBox ()
    self._scrollbar = gtk.VScrollbar (self._vte.get_adjustment ())
    if self.defaults['scrollbar']:
      self._scrollbar.show ()

    self._box.pack_start (self._vte)
    self._box.pack_start (self._scrollbar, False)

    self.gconf_client.notify_add (self.profile, self.on_gconf_notification)
    self.gconf_client.notify_add ('/apps/metacity/general/focus_mode', self.on_gconf_notification)

    self._vte.connect ("button-press-event", self.on_vte_button_press)
    self._vte.connect ("popup-menu", self.on_vte_popup_menu)
    if self.defaults['child_restart']:
      self._vte.connect ("child-exited", lambda term: self._vte.fork_command ())

    self._vte.add_events (gtk.gdk.ENTER_NOTIFY_MASK)
    self._vte.connect ("enter_notify_event", self.on_vte_notify_enter)

    self._vte.match_add ('((%s://(%s@)?)|(www|ftp)[%s]*\\.)[%s.]+(:[0-9]*)?'%(self.defaults['link_scheme'], self.defaults['link_user'], self.defaults['link_hostchars'], self.defaults['link_hostchars']))
    self._vte.match_add ('((%s://(%s@)?)|(www|ftp)[%s]*\\.)[%s.]+(:[0-9]+)?/[-A-Za-z0-9_$.+!*(),;:@&=?/~#%%]*[^]\'.}>) \t\r\n,\\\]'%(self.defaults['link_scheme'], self.defaults['link_userchars'], self.defaults['link_hostchars'], self.defaults['link_hostchars']))

    self._vte.fork_command ()

  def reconfigure_vte (self):
    if ((self.lastreconfigure != 0) and (time.time () - self.lastreconfigure) < 5):
      # Rate limit
      return
    self.lastreconfigure = time.time ()

    # Set our emulation
    self._vte.set_emulation (self.defaults['emulation'])

    # Set our wordchars
    # FIXME: This shouldn't be hardcoded
    self._vte.set_word_chars ('-A-Za-z0-9./?%&#_+')

    # Set our mouselation
    # FIXME: This shouldn't be hardcoded
    self._vte.set_mouse_autohide (True)

    # Set our compatibility
    # FIXME: This shouldn't be hardcoded
    self._vte.set_backspace_binding ("VTE_ERASE_AUTO")
    self._vte.set_delete_binding ("VTE_ERASE_AUTO")

    # Set our font, preferably from gconf settings
    if self.gconf_client.get_bool (self.profile + "/use_system_font"):
      font_name = (self.gconf_client.get_string ("/desktop/gnome/interface/monospace_font_name") or self.defaults['font_name'])
    else:
      font_name = (self.gconf_client.get_string (self.profile + "/font") or self.defaults['font_name'])

    try:
      self._vte.set_font (pango.FontDescription (font_name))
    except:
      pass

    # Set our boldness
    self._vte.set_allow_bold (self.gconf_client.get_bool (self.profile + "/allow_bold") or self.defaults['allow_bold'])

    # Set our color scheme, preferably from gconf settings
    palette = self.gconf_client.get_string (self.profile + "/palette") or self.defaults['palette']
    if self.gconf_client.get_bool (self.profile + "/use_theme_colors") == True:
      fg_color = self._vte.get_style().fg[gtk.STATE_NORMAL]
      bg_color = self._vte.get_style().bg[gtk.STATE_NORMAL]
    else:
      fg_color = gtk.gdk.color_parse (self.gconf_client.get_string (self.profile + "/foreground_color") or self.defaults['foreground_color'])
      bg_color = gtk.gdk.color_parse (self.gconf_client.get_string (self.profile + "/background_color") or self.defaults['background_color'])

    colors = palette.split (':')
    palette = []
    for color in colors:
      palette.append (gtk.gdk.color_parse (color))
    self._vte.set_colors (fg_color, bg_color, palette)

    # Set our cursor blinkiness
    self._vte.set_cursor_blinks = (self.gconf_client.get_bool (self.profile + "/cursor_blinks") or self.defaults['cursor_blinks'])

    # Set our audible belliness
    self._vte.set_audible_bell = not (self.gconf_client.get_bool (self.profile + "/silent_bell") or self.defaults['audible_bell'])
    self._vte.set_visible_bell (self.defaults['visible_bell'])

    # Set our scrolliness
    self._vte.set_scrollback_lines (self.gconf_client.get_int (self.profile + "/scrollback_lines") or self.defaults['scrollback_lines'])
    self._vte.set_scroll_on_keystroke (self.gconf_client.get_bool (self.profile + "/scroll_on_keystroke") or self.defaults['scroll_on_keystroke'])
    self._vte.set_scroll_on_output (self.gconf_client.get_bool (self.profile + "/scroll_on_output") or self.defaults['scroll_on_output'])

    # Set our sloppiness
    self.focus = self.gconf_client.get_string ("/apps/metacity/general/focus_mode") or self.defaults['focus']

  def on_gconf_notification (self, client, cnxn_id, entry, what):
    self.reconfigure_vte ()

  def on_vte_button_press (self, term, event):
    # Left mouse button should transfer focus to this vte widget
    if event.button == 1:
      self._vte.grab_focus ()
      return False

    # Right mouse button should display a context menu
    if event.button == 3:
      self.do_popup (event)
      return True

  def on_vte_notify_enter (self, term, event):
    if (self.focus == "sloppy" or self.focus == "mouse"):
      term.grab_focus ()
 	    # FIXME: Should we eat this event or let it propagate further?
      return False

  def do_scrollbar_toggle (self):
    if self._scrollbar.get_property ('visible'):
      self._scrollbar.hide ()
    else:
      self._scrollbar.show ()

  def on_vte_popup_menu (self, term):
    self.do_popup ()

  def do_popup (self, event = None):
    menu = self.create_popup_menu (event)
    menu.popup (None, None, None, event.button, event.time)

  def create_popup_menu (self, event):
    menu = gtk.Menu ()

    url = self._vte.match_check (int(event.x / self._vte.get_char_width ()), int(event.y / self._vte.get_char_height()))
    if url:
      item = gtk.MenuItem ("_Open Link")
      item.connect ("activate", lambda menu_item: gnome.url_show (url[0]))
      menu.append (item)

      item = gtk.MenuItem ("_Copy Link Address")
      item.connect ("activate", lambda menu_item: self.clipboard.set_text (url[0]))
      menu.append (item)

      item = gtk.MenuItem ()
      menu.append (item)

    item = gtk.ImageMenuItem (gtk.STOCK_COPY)
    item.connect ("activate", lambda menu_item: self._vte.copy_clipboard ())
    item.set_sensitive (self._vte.get_has_selection ())
    menu.append (item)

    item = gtk.ImageMenuItem (gtk.STOCK_PASTE)
    item.connect ("activate", lambda menu_item: self._vte.paste_clipboard ())
    menu.append (item)

    item = gtk.MenuItem ()
    menu.append (item)

    item = gtk.CheckMenuItem ("Show scrollbar")
    item.set_active (self._scrollbar.get_property ('visible'))
    item.connect ("toggled", lambda menu_item: self.do_scrollbar_toggle ())
    menu.append (item)

    menu.show_all ()
    return menu

  def get_box (self):
    return self._box

class Terminator:
  def __init__ (self):
    self.gconf_client = gconf.client_get_default ()

    self.window = gtk.Window ()
    self.icon = self.window.render_icon (gtk.STOCK_DIALOG_INFO, gtk.ICON_SIZE_BUTTON)
    self.window.set_icon (self.icon)
    self.window.connect ("delete_event", self.on_delete_event)
    self.window.connect ("destroy", self.on_destroy_event)
    self.window.maximize ()

  def on_delete_event (self, widget, event, data=None):
    dialog = gtk.Dialog ("Quit?", self.window, gtk.DIALOG_MODAL, (gtk.STOCK_CANCEL, gtk.RESPONSE_REJECT, gtk.STOCK_QUIT, gtk.RESPONSE_ACCEPT))
    label = gtk.Label("Do you really want to quit?")
    dialog.vbox.pack_start(label, True, True, 0)
    label.show ()

    res = dialog.run()
    if res == gtk.RESPONSE_ACCEPT:
      return False
    dialog.destroy ()
    return True

  def on_destroy_event (self, widget, data=None):
    gtk.main_quit ()

if __name__ == '__main__':
  term = Terminator ()

  t1 = TerminatorTerm (term)
  t2 = TerminatorTerm (term)
  t3 = TerminatorTerm (term)
  t4 = TerminatorTerm (term)

  pane1 = gtk.HPaned ()
  pane1.add1 (t1.get_box ())
  pane1.add2 (t2.get_box ())

  pane2 = gtk.HPaned ()
  pane2.add1 (t3.get_box ())
  pane2.add2 (t4.get_box ())

  vpane = gtk.VPaned ()
  vpane.add1 (pane1)
  vpane.add2 (pane2)

  term.window.add (vpane)
  term.window.show_all ()

  gtk.main ()
