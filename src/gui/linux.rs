
use glib;
use gtk::{
    self, MenuShellExt, GtkMenuItemExt, WidgetExt
};
use libappindicator::{AppIndicator, AppIndicatorStatus};
use std::{
    self,
    cell::RefCell,
    collections::HashMap,
    sync::mpsc::{channel, Sender, Receiver},
    thread,
    error,
    fmt,
    fs,
};

use tempfile;
//use crossbeam;

use crate::punwrap_r;
use crate::config::Config;
use crate::global::Global;

pub fn open_gui(args: &Vec<String>, config: &Config, global: &Global) {
  let icon_tmp = tempfile::Builder::new()
                    .suffix(".png")
                    .rand_bytes(5)
                    .tempfile().expect("Could not make temp file for icon");
                    
  if let Err(e) = fs::write(icon_tmp.path(), super::ICON_PNG) {
    println!("Error writing temp icon png: {:?}", e);
  }

  if let Ok(mut app) = Application::new() {

    punwrap_r!(app.set_icon_from_file( &icon_tmp.path().to_string_lossy() ));

    let hostname_s = format!("h: {}", config.hostname);
    app.add_menu_item(&hostname_s, |_| {
        
        // TODO real menu items
        println!("Printing a thing!");
  
        Ok::<_, Error>(())
    }).unwrap();

    app.add_menu_item("dis_i=first", |_| -> Result<(), Error> {
        println!("Printing dis_i=first");
        Ok(())
    }).unwrap();

    // We perform a double mutable borrow of `app` on a seperate thread.
    // This is seriously unsafe but graphics is always like that.
    let app_ptr = &mut app as *mut _;
    let app_ptr_i: usize = unsafe { std::mem::transmute(app_ptr) };
    thread::spawn(move || {
        let app_ptr: *mut _ = unsafe { std::mem::transmute(app_ptr_i) };
        let app: &mut Application = unsafe { &mut *app_ptr };
        let mut i = 0;
        loop {
            std::thread::sleep( std::time::Duration::from_millis(800) );
            let dis_i = i;
            app.set_menu_item(1, &format!("dis_i={}", dis_i), move |_| {
                
                // TODO real menu items
                println!("Printing a dis_i={}", dis_i);
          
                Ok::<_, Error>(())
            }).unwrap();
            i += 1;
        }
    });

    app.add_menu_item("quit", |_| -> Result<(), Error> {
        std::process::exit(0)
    }).unwrap();


    if let Err(e) = app.wait_for_message() {
      println!("e={:?}", e);
    }
  }
}

/*
 * Everything below is mostly a copy/paste from systray-rs,
 * but as new needs are added (update menu text, add icon from &[u8], etc.)
 * the implementation will drift quite a bit.
 */



// Gtk specific struct that will live only in the Gtk thread, since a lot of the
// base types involved don't implement Send (for good reason).
pub struct GtkSystrayApp {
    menu: gtk::Menu,
    ai: RefCell<AppIndicator>,
    menu_items: RefCell<HashMap<u32, gtk::MenuItem>>,
    event_tx: Sender<SystrayEvent>,
}

thread_local!(static GTK_STASH: RefCell<Option<GtkSystrayApp>> = RefCell::new(None));

// struct MenuItemInfo {
//     mid: u32,
//     title: String,
//     tooltip: String,
//     disabled: bool,
//     checked: bool,
// }

//type GtkCallback = Box<(Fn(&GtkSystrayApp) -> () + 'static)>;

// Convenience function to clean up thread local unwrapping
fn run_on_gtk_thread<F>(f: F)
where
    F: std::ops::Fn(&GtkSystrayApp) -> () + Send + 'static,
{
    // Note this is glib, not gtk. Calling gtk::idle_add will panic us due to
    // being on different threads. glib::idle_add can run across threads.
    glib::idle_add(move || {
        GTK_STASH.with(|stash| {
            let stash = stash.borrow();
            let stash = stash.as_ref();
            if let Some(stash) = stash {
                f(stash);
            }
        });
        gtk::prelude::Continue(false)
    });
}

impl GtkSystrayApp {
    pub fn new(event_tx: Sender<SystrayEvent>) -> Result<GtkSystrayApp, Error> {
        if let Err(e) = gtk::init() {
            return Err(Error::OsError(format!("{}", "Gtk init error!")));
        }
        let mut m = gtk::Menu::new();
        let mut ai = AppIndicator::new("", "");
        ai.set_status(AppIndicatorStatus::Active);
        ai.set_menu(&mut m);
        Ok(GtkSystrayApp {
            menu: m,
            ai: RefCell::new(ai),
            menu_items: RefCell::new(HashMap::new()),
            event_tx: event_tx,
        })
    }

    pub fn systray_menu_selected(&self, menu_id: u32) {
        self.event_tx
            .send(SystrayEvent {
                menu_index: menu_id as u32,
            })
            .ok();
    }

    pub fn add_menu_separator(&self, item_idx: u32) {
        //let mut menu_items = self.menu_items.borrow_mut();
        let m = gtk::SeparatorMenuItem::new();
        self.menu.append(&m);
        //menu_items.insert(item_idx, m);
        self.menu.show_all();
    }

    pub fn add_menu_entry(&self, item_idx: u32, item_name: &str) {
        let mut menu_items = self.menu_items.borrow_mut();
        if menu_items.contains_key(&item_idx) {
            let m: &gtk::MenuItem = menu_items.get(&item_idx).unwrap();
            m.set_label(item_name);
            self.menu.show_all();
            return;
        }
        let m = gtk::MenuItem::new_with_label(item_name);
        self.menu.append(&m);
        m.connect_activate(move |_| {
            run_on_gtk_thread(move |stash: &GtkSystrayApp| {
                stash.systray_menu_selected(item_idx);
            });
        });
        menu_items.insert(item_idx, m);
        self.menu.show_all();
    }

    pub fn set_menu_item(&self, item_idx: u32, item_name: &str) {
        let menu_items = self.menu_items.borrow_mut();
        if menu_items.contains_key(&item_idx) {
            let m: &gtk::MenuItem = menu_items.get(&item_idx).unwrap();
            m.set_label(item_name);
            self.menu.show_all();
        }
    }

    pub fn set_icon_from_file(&self, file: &str) {
        let mut ai = self.ai.borrow_mut();
        ai.set_icon_full(file, "icon");
    }
}

#[allow(dead_code)]
struct Window {
    gtk_loop: Option<thread::JoinHandle<()>>,
}

#[allow(dead_code)]
impl Window {
    pub fn new(event_tx: Sender<SystrayEvent>) -> Result<Window, Error> {
        let (tx, rx) = channel();
        let gtk_loop = thread::spawn(move || {
            GTK_STASH.with(|stash| match GtkSystrayApp::new(event_tx) {
                Ok(data) => {
                    (*stash.borrow_mut()) = Some(data);
                    punwrap_r!(tx.send(Ok(())));
                }
                Err(e) => {
                    punwrap_r!(tx.send(Err(e)), return);
                }
            });
            gtk::main();
        });
        match rx.recv().unwrap() {
            Ok(()) => Ok(Window {
                gtk_loop: Some(gtk_loop),
            }),
            Err(e) => Err(e),
        }
    }

    pub fn add_menu_entry(&self, item_idx: u32, item_name: &str) -> Result<(), Error> {
        let n = item_name.to_owned().clone();
        run_on_gtk_thread(move |stash: &GtkSystrayApp| {
            stash.add_menu_entry(item_idx, &n);
        });
        Ok(())
    }

    pub fn set_menu_entry(&self, item_idx: u32, item_name: &str) -> Result<(), Error> {
        let n = item_name.to_owned().clone();
        run_on_gtk_thread(move |stash: &GtkSystrayApp| {
            stash.set_menu_item(item_idx, &n);
        });
        Ok(())
    }

    pub fn add_menu_separator(&self, item_idx: u32) -> Result<(), Error> {
        run_on_gtk_thread(move |stash: &GtkSystrayApp| {
            stash.add_menu_separator(item_idx);
        });
        Ok(())
    }

    pub fn set_icon_from_file(&self, file: &str) -> Result<(), Error> {
        let n = file.to_owned().clone();
        run_on_gtk_thread(move |stash: &GtkSystrayApp| {
            stash.set_icon_from_file(&n);
        });
        Ok(())
    }

    pub fn set_icon_from_resource(&self, resource: &str) -> Result<(), Error> {
        panic!("Not implemented on this platform!");
    }

    pub fn shutdown(&self) -> Result<(), Error> {
        Ok(())
    }

    pub fn set_tooltip(&self, tooltip: &str) -> Result<(), Error> {
        panic!("Not implemented on this platform!");
    }

    pub fn quit(&self) {
        glib::idle_add(|| {
            gtk::main_quit();
            glib::Continue(false)
        });
    }
}


type BoxedError = Box<dyn error::Error + Send + Sync + 'static>;

#[allow(dead_code)]
#[derive(Debug)]
pub enum Error {
    OsError(String),
    NotImplementedError,
    UnknownError,
    Error(BoxedError),
}

impl From<BoxedError> for Error {
    fn from(value: BoxedError) -> Self {
        Error::Error(value)
    }
}

pub struct SystrayEvent {
    menu_index: u32,
}

impl error::Error for Error {}

impl fmt::Display for Error {
    fn fmt(&self, f: &mut fmt::Formatter) -> Result<(), fmt::Error> {
        use self::Error::*;

        match *self {
            OsError(ref err_str) => write!(f, "OsError: {}", err_str),
            NotImplementedError => write!(f, "Functionality is not implemented yet"),
            UnknownError => write!(f, "Unknown error occurrred"),
            Error(ref e) => write!(f, "Error: {}", e),
        }
    }
}

pub struct Application {
    window: Window,
    menu_idx: u32,
    callback: HashMap<u32, Callback>,
    // Each platform-specific window module will set up its own thread for
    // dealing with the OS main loop. Use this channel for receiving events from
    // that thread.
    rx: Receiver<SystrayEvent>,
}

type Callback =
    Box<(dyn FnMut(&mut Application) -> Result<(), BoxedError> + Send + Sync + 'static)>;

fn make_callback<F, E>(mut f: F) -> Callback
where
    F: FnMut(&mut Application) -> Result<(), E> + Send + Sync + 'static,
    E: error::Error + Send + Sync + 'static,
{
    Box::new(move |a: &mut Application| match f(a) {
        Ok(()) => Ok(()),
        Err(e) => Err(Box::new(e) as BoxedError),
    }) as Callback
}

#[allow(dead_code)]
impl Application {
    pub fn new() -> Result<Application, Error> {
        let (event_tx, event_rx) = channel();
        match Window::new(event_tx) {
            Ok(w) => Ok(Application {
                window: w,
                menu_idx: 0,
                callback: HashMap::new(),
                rx: event_rx,
            }),
            Err(e) => Err(e),
        }
    }

    pub fn add_menu_item<F, E>(&mut self, item_name: &str, f: F) -> Result<u32, Error>
    where
        F: FnMut(&mut Application) -> Result<(), E> + Send + Sync + 'static,
        E: error::Error + Send + Sync + 'static,
    {
        let idx = self.menu_idx;
        if let Err(e) = self.window.add_menu_entry(idx, item_name) {
            return Err(e);
        }
        self.callback.insert(idx, make_callback(f));
        self.menu_idx += 1;
        Ok(idx)
    }

    pub fn set_menu_item<F, E>(&mut self, idx: u32, item_name: &str, f: F) -> Result<u32, Error>
    where
        F: FnMut(&mut Application) -> Result<(), E> + Send + Sync + 'static,
        E: error::Error + Send + Sync + 'static,
    {
        if let Err(e) = self.window.set_menu_entry(idx, item_name) {
            return Err(e);
        }
        self.callback.insert(idx, make_callback(f));
        Ok(idx)
    }

    pub fn add_menu_separator(&mut self) -> Result<u32, Error> {
        let idx = self.menu_idx;
        if let Err(e) = self.window.add_menu_separator(idx) {
            return Err(e);
        }
        self.menu_idx += 1;
        Ok(idx)
    }

    pub fn set_icon_from_file(&self, file: &str) -> Result<(), Error> {
        self.window.set_icon_from_file(file)
    }

    pub fn set_icon_from_resource(&self, resource: &str) -> Result<(), Error> {
        self.window.set_icon_from_resource(resource)
    }

    #[cfg(target_os = "windows")]
    pub fn set_icon_from_buffer(
        &self,
        buffer: &[u8],
        width: u32,
        height: u32,
    ) -> Result<(), Error> {
        self.window.set_icon_from_buffer(buffer, width, height)
    }

    pub fn shutdown(&self) -> Result<(), Error> {
        self.window.shutdown()
    }

    pub fn set_tooltip(&self, tooltip: &str) -> Result<(), Error> {
        self.window.set_tooltip(tooltip)
    }

    pub fn quit(&mut self) {
        self.window.quit()
    }

    pub fn wait_for_message(&mut self) -> Result<(), Error> {
        loop {
            let msg;
            match self.rx.recv() {
                Ok(m) => msg = m,
                Err(_) => {
                    self.quit();
                    break;
                }
            }
            if self.callback.contains_key(&msg.menu_index) {
                if let Some(mut f) = self.callback.remove(&msg.menu_index) {
                    f(self)?;
                    self.callback.insert(msg.menu_index, f);
                }
            }
        }

        Ok(())
    }
}

impl Drop for Application {
    fn drop(&mut self) {
        self.shutdown().ok();
    }
}

